"""
Twilio Voice — intégration téléphonique temps réel.

Flux :
  📞 Appel → Twilio → POST /twilio/incoming → TwiML (Media Stream)
             → WS /twilio/stream
             → Voxtral real-time STT (streaming) → Agent Mistral
             → ElevenLabs (TTS → PCM 8kHz → mulaw) → Twilio → appelant
"""

import asyncio
import audioop
import base64
import json
import os
import uuid
import numpy as np
from datetime import datetime

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Request
from fastapi.responses import Response
from dotenv import load_dotenv

from db import update_call, get_all_calls
from socket_manager import manager
from agent import Agent
from prompts import SYSTEM_PROMPT
from stt import transcribe_pcm
from tts import speak_pcm

load_dotenv()

router = APIRouter(prefix="/twilio")

# ── Audio constants ───────────────────────────────────────────────────────────
MULAW_RATE      = 8000
CHUNK_BYTES     = 160          # 20 ms de mulaw à 8 kHz
SPEECH_THRESH   = 400          # RMS energy au-dessus = parole détectée
SILENCE_CHUNKS  = 40           # 40 × 20 ms = 800 ms de silence → fin d'énoncé
MIN_SPEECH      = 15           # 15 × 20 ms = 300 ms minimum de parole


# ── Audio helpers ─────────────────────────────────────────────────────────────

def pcm_to_mulaw_chunks(pcm_bytes: bytes) -> list[str]:
    """PCM 16-bit 8kHz → liste de payloads mulaw base64 (chunks de 20ms)."""
    mulaw = audioop.lin2ulaw(pcm_bytes, 2)
    return [
        base64.b64encode(mulaw[i: i + CHUNK_BYTES]).decode()
        for i in range(0, len(mulaw), CHUNK_BYTES)
    ]


async def send_audio(ws: WebSocket, stream_sid: str, pcm_bytes: bytes):
    """Envoie du PCM 8kHz à Twilio en chunks mulaw temps-réel."""
    chunks = pcm_to_mulaw_chunks(pcm_bytes)
    for payload in chunks:
        await ws.send_text(json.dumps({
            "event": "media",
            "streamSid": stream_sid,
            "media": {"payload": payload},
        }))
        await asyncio.sleep(0.02)   # rythme temps-réel (1 chunk = 20ms)


# ── Twilio webhook ────────────────────────────────────────────────────────────

@router.post("/incoming")
async def incoming_call(request: Request):
    """
    Twilio appelle ce webhook quand quelqu'un compose le numéro.
    Retourne du TwiML qui démarre un Media Stream vers notre WebSocket.
    """
    public_url = os.getenv("PUBLIC_URL", "")
    if not public_url:
        public_url = request.headers.get("host", "localhost:8000")

    twiml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
  <Connect>
    <Stream url="wss://{public_url}/twilio/stream" />
  </Connect>
</Response>"""
    return Response(content=twiml, media_type="application/xml")


# ── Media Stream WebSocket ────────────────────────────────────────────────────

@router.websocket("/stream")
async def twilio_stream(websocket: WebSocket):
    await websocket.accept()

    agent      = Agent(system_prompt=SYSTEM_PROMPT)
    call_id    = str(uuid.uuid4())
    stream_sid = None

    # VAD state
    pcm_buffer     = bytearray()
    silence_count  = 0
    speech_count   = 0
    recording      = False
    agent_speaking = False    # True pendant qu'on envoie du TTS
    last_geocoded  = None
    dispatch_sent  = False

    # Enregistrer l'appel dans la DB
    update_call(call_id, {
        "id":         call_id,
        "mode":       "twilio",
        "time":       datetime.now().isoformat(),
        "transcript": agent.get_transcript(),
    })
    await manager.broadcast({"event": "db_response", "data": get_all_calls()})

    loop = asyncio.get_running_loop()

    try:
        while True:
            raw = await websocket.receive_text()
            msg = json.loads(raw)
            event = msg.get("event")

            # ── Stream démarré ────────────────────────────────────────────────
            if event == "start":
                stream_sid = msg["start"]["streamSid"]
                print(f"[TWILIO] Stream démarré : {stream_sid}")

                # Salutation initiale via ElevenLabs
                try:
                    greeting_pcm = await loop.run_in_executor(
                        None, speak_pcm, "9-1-1, what's your emergency?"
                    )
                    agent_speaking = True
                    await send_audio(websocket, stream_sid, greeting_pcm)
                    print("[TWILIO] Salutation envoyée.")
                except Exception as tts_err:
                    print(f"[TWILIO] Erreur TTS salutation : {tts_err}")
                finally:
                    agent_speaking = False
                    pcm_buffer.clear()
                    recording     = False
                    silence_count = 0
                    speech_count  = 0

            # ── Chunk audio entrant ───────────────────────────────────────────
            elif event == "media":
                # Ignorer l'audio sortant (notre propre TTS renvoyé par Twilio)
                track = msg["media"].get("track", "inbound")
                if track in ("outbound", "outbound_track"):
                    continue

                # Décoder mulaw → PCM
                mulaw_bytes = base64.b64decode(msg["media"]["payload"])
                pcm_chunk   = audioop.ulaw2lin(mulaw_bytes, 2)

                # VAD simple par énergie RMS
                samples = np.frombuffer(pcm_chunk, dtype=np.int16)
                rms     = float(np.sqrt(np.mean(samples.astype(np.float32) ** 2)))

                # Ignorer l'audio entrant pendant que l'agent parle
                if agent_speaking:
                    continue

                if rms > SPEECH_THRESH:
                    recording     = True
                    silence_count = 0
                    speech_count += 1
                    pcm_buffer.extend(pcm_chunk)

                elif recording:
                    silence_count += 1
                    pcm_buffer.extend(pcm_chunk)

                    if silence_count >= SILENCE_CHUNKS and speech_count >= MIN_SPEECH:
                        # ── Fin d'énoncé → transcription batch ────────────────
                        audio_data    = bytes(pcm_buffer)
                        pcm_buffer.clear()
                        recording     = False
                        silence_count = 0
                        speech_count  = 0

                        text = await loop.run_in_executor(None, transcribe_pcm, audio_data)
                        if not text:
                            continue

                        print(f"[TWILIO] Caller: '{text}'")

                        # ── Agent Mistral ─────────────────────────────────────
                        chat_history = [
                            {"role": "system", "content": SYSTEM_PROMPT}
                        ] + [
                            {"role": m["role"], "content": m["content"]}
                            for m in agent.standard_transcript
                        ]

                        response_text = ""
                        async for chunk_json in agent.get_responses(text, chat_history):
                            d = json.loads(chunk_json)
                            if d["type"] == "assistant_input":
                                response_text += d["text"]

                        print(f"[TWILIO] Dispatcher: '{response_text}'")

                        # Mise à jour transcript + dashboard
                        update_call(call_id, {"transcript": agent.get_transcript()})
                        await manager.broadcast({"event": "db_response", "data": get_all_calls()})

                        # ── TTS de la réponse principale ─────────────────────
                        if response_text and stream_sid:
                            try:
                                tts_pcm = await loop.run_in_executor(None, speak_pcm, response_text)
                                agent_speaking = True
                                await send_audio(websocket, stream_sid, tts_pcm)
                            except Exception as tts_err:
                                print(f"[TWILIO] Erreur TTS réponse : {tts_err}")
                            finally:
                                # Réinitialiser le VAD après le TTS pour repartir proprement
                                agent_speaking = False
                                pcm_buffer.clear()
                                recording     = False
                                silence_count = 0
                                speech_count  = 0

                        # ── Extraction des infos ──────────────────────────────
                        extracted = await agent.extract_call_info()
                        if extracted:
                            update_call(call_id, extracted)
                            location = extracted.get("location_name")
                            if location and location != last_geocoded:
                                geo = await agent.geocode_location(location)
                                if geo:
                                    update_call(call_id, geo)
                                    last_geocoded = location

                                    from emergency_services import find_nearest, get_route
                                    from db import get_call
                                    import agent as agent_module
                                    call_type = extracted.get("type") or get_call(call_id).get("type")
                                    coords    = geo.get("coordinates")
                                    if call_type and coords and agent_module.EMERGENCY_REGISTRY:
                                        nearest = find_nearest(
                                            coords["lat"], coords["lng"],
                                            call_type, agent_module.EMERGENCY_REGISTRY
                                        )
                                        if nearest:
                                            route = await loop.run_in_executor(
                                                None, get_route,
                                                nearest["lat"], nearest["lng"],
                                                coords["lat"], coords["lng"],
                                            )
                                            nearest["route"] = route
                                            update_call(call_id, {"nearest_service": nearest})

                                            if not dispatch_sent:
                                                dispatch_sent = True
                                                dispatch_text = await agent.generate_dispatch_message(nearest)
                                                agent.standard_transcript.append(
                                                    {"role": "assistant", "content": dispatch_text}
                                                )
                                                update_call(call_id, {"transcript": agent.get_transcript()})
                                                try:
                                                    dispatch_pcm = await loop.run_in_executor(
                                                        None, speak_pcm, dispatch_text
                                                    )
                                                    agent_speaking = True
                                                    await send_audio(websocket, stream_sid, dispatch_pcm)
                                                except Exception as tts_err:
                                                    print(f"[TWILIO] Erreur TTS dispatch : {tts_err}")
                                                finally:
                                                    agent_speaking = False
                                                    pcm_buffer.clear()
                                                    recording     = False
                                                    silence_count = 0
                                                    speech_count  = 0

                            await manager.broadcast({"event": "db_response", "data": get_all_calls()})

            # ── Fin du stream ─────────────────────────────────────────────────
            elif event == "stop":
                print(f"[TWILIO] Appel terminé — call_id={call_id}")
                break

    except (WebSocketDisconnect, Exception) as e:
        print(f"[TWILIO] Déconnexion : {e}")
