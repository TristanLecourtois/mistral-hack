import json
import re
import os
from mistralai import Mistral

_MD_RE = re.compile(r'\*{1,3}([^*\n]*)\*{1,3}|_{1,2}([^_\n]*)_{1,2}')

def _strip_markdown(text: str) -> str:
    """Retire le formatage markdown (bold/italic) du texte."""
    return _MD_RE.sub(lambda m: (m.group(1) or m.group(2) or '').strip(), text)
import inflect
from fastapi import WebSocket, APIRouter, WebSocketDisconnect
import asyncio
import uuid
from datetime import datetime
from db import update_call, get_call, get_all_calls
from socket_manager import manager
from prompts import SYSTEM_PROMPT, EXTRACTION_PROMPT
from geocoding import geocode, street_view_url
from emergency_services import find_nearest, get_route

# Rempli au démarrage par main.py via lifespan
EMERGENCY_REGISTRY: dict = {}
import os
from dotenv import load_dotenv
load_dotenv()

router = APIRouter(prefix="/voxtral")


@router.websocket("")
async def voxtral_endpoint(websocket: WebSocket):
    await websocket.accept()

    agent = Agent(system_prompt=SYSTEM_PROMPT)
    last_history = []
    id = str(uuid.uuid4())
    last_geocoded_location = None
    dispatch_sent = False  # envoie le message de dispatch une seule fois

    # Greeting initial — le dispatcher parle en premier
    greeting = "9-1-1, what's your emergency?"
    await websocket.send_text(json.dumps({"type": "assistant_input", "text": greeting}))
    await websocket.send_text(json.dumps({"type": "assistant_end"}))
    update_call(id, {
        "id": id,
        "mode": "voxtral",
        "time": datetime.now().isoformat(),
        "transcript": agent.get_transcript(),
    })
    await manager.broadcast({"event": "db_response", "data": get_all_calls()})

    try:
        while True:
            data = await websocket.receive_text()
            socket_message = json.loads(data)

            message, chat_history, transcript = agent.parse_voxtral_message(
                socket_message
            )
            last_history = chat_history

            updated_data = {
                "id": id,
                "mode": "voxtral",
                "time": datetime.now().isoformat(),
                "transcript": transcript + [{"role": "user", "content": message}],
            }

            update_call(id, updated_data)
            all_calls = get_all_calls()

            await manager.broadcast(
                {"event": "db_response", "data": all_calls}
            )

            responses = agent.get_responses(message, last_history)

            async for response in responses:
                await websocket.send_text(response)

            await asyncio.sleep(0.1)

            # Mise à jour du transcript
            update_call(id, {
                "time": datetime.now().isoformat(),
                "transcript": agent.get_transcript(),
            })

            # Extraction automatique des infos clés
            extracted = await agent.extract_call_info()
            if extracted:
                update_call(id, extracted)
                print(f"[EXTRACTED] {extracted}")

                # Géocodage si une nouvelle localisation a été détectée
                location = extracted.get("location_name")
                if location and location != last_geocoded_location:
                    geo = await agent.geocode_location(location)
                    if geo:
                        update_call(id, geo)
                        last_geocoded_location = location
                        print(f"[GEO] {geo}")

                        # Service d'urgence le plus proche
                        call_type = extracted.get("type") or get_call(id).get("type")
                        coords = geo.get("coordinates")
                        print(f"[DEBUG] type={call_type} coords={coords} registry_keys={list(EMERGENCY_REGISTRY.keys())} sizes={[len(v) for v in EMERGENCY_REGISTRY.values()]}")
                        if call_type and coords and EMERGENCY_REGISTRY:
                            nearest = find_nearest(
                                coords["lat"], coords["lng"],
                                call_type, EMERGENCY_REGISTRY
                            )
                            if nearest:
                                # Itinéraire réel via OSRM
                                route = await asyncio.get_running_loop().run_in_executor(
                                    None, get_route,
                                    nearest["lat"], nearest["lng"],
                                    coords["lat"], coords["lng"],
                                )
                                nearest["route"] = route
                                update_call(id, {"nearest_service": nearest})
                                print(f"[NEAREST] {nearest['name']} ({nearest['distance_km']} km)")

                                # Message de dispatch (une seule fois)
                                if not dispatch_sent:
                                    dispatch_sent = True
                                    dispatch_text = await agent.generate_dispatch_message(nearest)
                                    agent.standard_transcript.append(
                                        {"role": "assistant", "content": dispatch_text}
                                    )
                                    update_call(id, {"transcript": agent.get_transcript()})
                                    await websocket.send_text(json.dumps({"type": "assistant_input", "text": dispatch_text}))
                                    await websocket.send_text(json.dumps({"type": "assistant_end"}))

            all_calls = get_all_calls()
            await manager.broadcast({"event": "db_response", "data": all_calls})

            current_data = str(get_call(id))
            print(current_data)

    except WebSocketDisconnect:
        print("WebSocket connection has been closed.")


class Agent:
    def __init__(self, *, system_prompt: str):
        self.system_prompt = system_prompt
        self.standard_transcript = []

        self.client = Mistral(api_key=os.getenv("MISTRAL_API_KEY"))
        self.model = "ministral-8b-latest"
        self.temperature = 0.8
        self.max_tokens = 1024
        self.p = inflect.engine()
        # Le dispatcher parle toujours en premier
        self.standard_transcript = [
            {"role": "assistant", "content": "9-1-1, what's your emergency?"}
        ]

    async def get_responses(self, message: str, chat_history=None):
        """
        Récupère les réponses de l'API Mistral avec streaming.
        Convertit les nombres en lettres et envoie les chunks par WebSocket.
        """
        if chat_history is None:
            chat_history = []

        self.standard_transcript.append(
            {"role": "user", "content": message}
        )

        # Construire la liste des messages pour l'API
        # Filtrer les messages Mistral au format simple (dict avec role/content)
        messages = []
        for msg in chat_history:
            if isinstance(msg, dict):
                # Format simple : {"role": "user", "content": "..."}
                messages.append(msg)
            else:
                # Format LangChain (HumanMessage, AIMessage, SystemMessage)
                # Extraire le contenu et déterminer le rôle
                if hasattr(msg, 'content'):
                    if msg.__class__.__name__ == 'HumanMessage':
                        messages.append({"role": "user", "content": msg.content})
                    elif msg.__class__.__name__ == 'AIMessage':
                        messages.append({"role": "assistant", "content": msg.content})
                    elif msg.__class__.__name__ == 'SystemMessage':
                        # Le système est passé séparément
                        pass

        # Ajouter le nouveau message
        messages.append({"role": "user", "content": message})

        text = ""
        loop = asyncio.get_running_loop()
        queue = asyncio.Queue()

        def run_sync_stream():
            try:
                stream = self.client.chat.stream(
                    model=self.model,
                    messages=messages,
                    temperature=self.temperature,
                    max_tokens=self.max_tokens,
                )
                for event in stream:
                    # Extraire le contenu de la structure CompletionEvent
                    if hasattr(event, 'data') and event.data.choices:
                        delta_content = event.data.choices[0].delta.content
                        if delta_content:  # Ignorer les chunks vides
                            loop.call_soon_threadsafe(queue.put_nowait, ("chunk", delta_content))
            except Exception as e:
                loop.call_soon_threadsafe(queue.put_nowait, ("error", str(e)))
            finally:
                loop.call_soon_threadsafe(queue.put_nowait, ("done", None))

        loop.run_in_executor(None, run_sync_stream)

        try:
            while True:
                kind, value = await queue.get()
                if kind == "chunk":
                    output = _strip_markdown(value)
                    numbers = re.findall(r"\b\d{1,3}(?:,\d{3})*(?:\.\d+)?\b", output)
                    for number in numbers:
                        words = self.number_to_words(number)
                        output = output.replace(number, words, 1)
                    text += output
                    yield json.dumps({"type": "assistant_input", "text": output})
                elif kind == "error":
                    print(f"Erreur lors de l'appel API Mistral: {value}")
                    yield json.dumps({"type": "assistant_error", "text": f"Erreur: {value}"})
                    break
                elif kind == "done":
                    break
        except Exception as e:
            print(f"Erreur streaming: {e}")
            yield json.dumps({"type": "assistant_error", "text": str(e)})

        self.standard_transcript.append(
            {"role": "assistant", "content": text}
        )

        yield json.dumps({"type": "assistant_end"})

    def get_transcript(self):
        """Retourne l'historique des messages."""
        return self.standard_transcript

    async def generate_dispatch_message(self, service: dict) -> str:
        """
        Génère un message de dispatch dans la langue de l'appelant via Mistral.
        """
        recent = self.standard_transcript[-6:]
        transcript_text = "\n".join(f"{m['role'].upper()}: {m['content']}" for m in recent)
        type_labels = {"police": "police", "fire": "fire department", "hospital": "medical team"}
        service_label = type_labels.get(service["type"], "emergency services")

        messages = [
            {"role": "system", "content": (
                "You are a 911 dispatcher. Generate ONE brief, professional sentence "
                "to inform the caller that help is on the way. "
                "Include the service name and distance. "
                "ALWAYS reply in English. Be concise and reassuring."
            )},
            {"role": "user", "content": (
                f"Transcript:\n{transcript_text}\n\n"
                f"Nearest {service_label}: {service['name']}, {service['distance_km']} km away. "
                f"Generate the dispatch confirmation message."
            )},
        ]

        def sync_call():
            response = self.client.chat.complete(
                model=self.model,
                messages=messages,
                temperature=0.3,
                max_tokens=80,
            )
            return _strip_markdown(response.choices[0].message.content)

        loop = asyncio.get_running_loop()
        try:
            return await loop.run_in_executor(None, sync_call)
        except Exception as e:
            print(f"Erreur dispatch message: {e}")
            return f"The nearest {service['name']} is {service['distance_km']} km away. Help is on the way."

    async def geocode_location(self, location_name: str) -> dict:
        """
        Géocode une adresse, retourne coordinates + formatted_address + Bing Streetside.
        """
        def sync_geocode():
            result = geocode(location_name)
            if not result:
                return {}
            lat, lng = result["lat"], result["lng"]
            return {
                "coordinates": {"lat": lat, "lng": lng},
                "location_name": result["formatted_address"],
                "street_image": street_view_url(lat, lng),
            }

        loop = asyncio.get_running_loop()
        try:
            return await loop.run_in_executor(None, sync_geocode)
        except Exception as e:
            print(f"Erreur geocoding: {e}")
            return {}

    async def extract_call_info(self) -> dict:
        """
        Fait un appel Mistral rapide (non-streaming) pour extraire
        les infos structurées de l'appel à partir du transcript courant.
        """
        if len(self.standard_transcript) < 2:
            return {}

        transcript_text = "\n".join(
            f"{msg['role'].upper()}: {msg['content']}"
            for msg in self.standard_transcript
        )

        messages = [
            {"role": "system", "content": EXTRACTION_PROMPT},
            {"role": "user", "content": f"Transcript:\n{transcript_text}"},
        ]

        def sync_extract():
            response = self.client.chat.complete(
                model="ministral-8b-latest",
                messages=messages,
                temperature=0.1,
                max_tokens=512,
            )
            return response.choices[0].message.content

        loop = asyncio.get_running_loop()
        try:
            raw = await loop.run_in_executor(None, sync_extract)
            raw = raw.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
            return json.loads(raw)
        except Exception as e:
            print(f"Erreur extraction infos: {e}")
            return {}

    def parse_voxtral_message(self, messages_payload: dict):
        """
        Parse les messages Voxtral et construit l'historique.
        Convertit les messages LangChain en dictionnaires simples pour Mistral.
        """
        messages = messages_payload["messages"]
        last_user_message = messages[-1]["message"]["content"]

        chat_history = [{"role": "system", "content": self.system_prompt}]
        last_role = None
        combined_utterance = ""

        for message in messages[:-1]:
            message_object = message["message"]
            current_role = message_object["role"]

            if current_role == "user":
                if last_role == "assistant" and combined_utterance:
                    chat_history.append(
                        {"role": "assistant", "content": combined_utterance}
                    )
                    combined_utterance = ""
                chat_history.append(
                    {"role": "user", "content": message_object["content"]}
                )

            elif current_role == "assistant":
                if last_role == "assistant":
                    combined_utterance += " " + message_object["content"]
                else:
                    if combined_utterance:
                        chat_history.append(
                            {"role": "assistant", "content": combined_utterance}
                        )
                    combined_utterance = message_object["content"]

            last_role = current_role

        if combined_utterance:
            chat_history.append(
                {"role": "assistant", "content": combined_utterance}
            )

        return [last_user_message, chat_history, self.standard_transcript]

    def number_to_words(self, number: str) -> str:
        """
        Convertit un nombre (chaîne de caractères) en lettres.
        Gère les formats avec virgules et décimales.
        """
        try:
            # Nettoyer le nombre
            clean_number = number.replace(",", "")
            # Convertir en float puis en int si pas de décimales
            num_float = float(clean_number)
            if num_float.is_integer():
                num_int = int(num_float)
                return self.p.number_to_words(num_int)
            else:
                return self.p.number_to_words(num_float)
        except (ValueError, AttributeError):
            return number