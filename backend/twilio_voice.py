"""
Twilio Voice — intégration téléphonique temps réel.

Flux :
  📞 Appel → Twilio → POST /twilio/incoming → TwiML (Media Stream)
             → WS /twilio/stream
             → Voxtral STT → Agent Mistral
             → ElevenLabs TTS → Twilio → appelant

Fonctionnalités :
  - Barge-in : l'agent s'arrête si l'utilisateur parle pendant le TTS
  - Fin d'appel : déclenchée par le dashboard ou par l'agent (mot "Goodbye")
  - Receiver tâche de fond : WebSocket toujours lu
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

from db import update_call, get_all_calls, get_call
from socket_manager import manager
from sms import send_call_summary_sms
from agent import Agent
from prompts import SYSTEM_PROMPT
from stt import transcribe_pcm
from tts import speak_pcm
from emergency_services import find_nearest, get_route
from voice_emotion import analyze_voice_emotion, MAX_HISTORY
import agent as agent_module

load_dotenv()

router = APIRouter(prefix="/twilio")

# call_id → asyncio.Event  (set pour fermer le stream depuis le dashboard)
active_streams: dict[str, asyncio.Event] = {}

# ── Audio constants ───────────────────────────────────────────────────────────
MULAW_RATE     = 8000
CHUNK_BYTES    = 160          # 20 ms de mulaw à 8 kHz
SPEECH_THRESH  = 400          # RMS → parole détectée
SILENCE_CHUNKS = 40           # 40 × 20 ms = 800 ms de silence
MIN_SPEECH     = 15           # 15 × 20 ms = 300 ms minimum de parole


# ── Audio helpers ─────────────────────────────────────────────────────────────

def pcm_to_mulaw_chunks(pcm_bytes: bytes) -> list[str]:
    mulaw = audioop.lin2ulaw(pcm_bytes, 2)
    return [
        base64.b64encode(mulaw[i: i + CHUNK_BYTES]).decode()
        for i in range(0, len(mulaw), CHUNK_BYTES)
    ]


# ── Twilio webhook ────────────────────────────────────────────────────────────

@router.post("/incoming")
async def incoming_call(request: Request):
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

    agent         = Agent(system_prompt=SYSTEM_PROMPT)
    call_id       = str(uuid.uuid4())
    stream_sid    = None
    loop          = asyncio.get_running_loop()
    close_event   = asyncio.Event()

    # VAD state
    pcm_buffer    = bytearray()
    silence_count = 0
    speech_count  = 0
    recording     = False

    # TTS state
    agent_speaking = False
    tts_task       = None     # asyncio.Task de lecture en cours

    last_geocoded  = None
    dispatch_sent  = False

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _reset_vad():
        nonlocal pcm_buffer, recording, silence_count, speech_count
        pcm_buffer.clear()
        recording     = False
        silence_count = 0
        speech_count  = 0

    async def _twilio_clear():
        if stream_sid:
            try:
                await websocket.send_text(json.dumps(
                    {"event": "clear", "streamSid": stream_sid}
                ))
            except Exception:
                pass

    async def _send_chunks(pcm: bytes, barge_flag: list):
        """Envoie les chunks mulaw. barge_flag[0]=True → arrêt immédiat."""
        for payload in pcm_to_mulaw_chunks(pcm):
            if barge_flag[0]:
                return
            try:
                await websocket.send_text(json.dumps({
                    "event": "media",
                    "streamSid": stream_sid,
                    "media": {"payload": payload},
                }))
            except Exception:
                return  # WebSocket fermé, on arrête silencieusement
            await asyncio.sleep(0.018)

    async def _play_tts_blocking(text: str):
        """Génère et joue le TTS en attendant la fin (sans barge-in). Pour la salutation."""
        nonlocal agent_speaking
        try:
            pcm = await loop.run_in_executor(None, speak_pcm, text)
            agent_speaking = True
            await _send_chunks(pcm, [False])   # pas de barge-in
        except Exception as e:
            print(f"[TTS] Erreur salutation : {e}")
        finally:
            agent_speaking = False
            _reset_vad()

    async def _play_tts_background(text: str) -> asyncio.Task:
        """Génère le TTS puis lance la lecture en tâche de fond (barge-in possible)."""
        nonlocal agent_speaking, tts_task
        try:
            pcm = await loop.run_in_executor(None, speak_pcm, text)
        except Exception as e:
            print(f"[TTS] Erreur : {e}")
            return None
        barge_flag = [False]
        agent_speaking = True
        _reset_vad()

        async def _runner():
            nonlocal agent_speaking
            try:
                await _send_chunks(pcm, barge_flag)
            except (asyncio.CancelledError, Exception):
                barge_flag[0] = True
            finally:
                agent_speaking = False
                _reset_vad()

        t = asyncio.create_task(_runner())
        tts_task = t
        # Attacher le flag au task pour pouvoir le stopper
        t._barge_flag = barge_flag
        return t

    async def _interrupt():
        """Arrête le TTS en cours + vide le buffer Twilio."""
        nonlocal agent_speaking, tts_task
        if tts_task and not tts_task.done():
            if hasattr(tts_task, "_barge_flag"):
                tts_task._barge_flag[0] = True
            tts_task.cancel()
            try:
                await tts_task
            except (asyncio.CancelledError, Exception):
                pass
        tts_task       = None
        agent_speaking = False
        await _twilio_clear()

    # ── Receiver WebSocket (tâche de fond) ────────────────────────────────────
    msg_queue = asyncio.Queue()

    async def _receiver():
        try:
            while True:
                raw = await websocket.receive_text()
                await msg_queue.put(raw)
        except Exception:
            await msg_queue.put(None)

    recv_task = asyncio.create_task(_receiver())

    # Enregistrer le stream pour le dashboard
    active_streams[call_id] = close_event
    update_call(call_id, {
        "id":         call_id,
        "mode":       "twilio",
        "time":       datetime.now().isoformat(),
        "transcript": agent.get_transcript(),
        "status":     "active",
    })
    await manager.broadcast({"event": "db_response", "data": get_all_calls()})

    try:
        while True:
            # Vérifier si le dashboard a demandé la fin
            if close_event.is_set():
                print(f"[TWILIO] Fin demandée par dashboard — {call_id}")
                break

            try:
                raw = await asyncio.wait_for(msg_queue.get(), timeout=0.3)
            except asyncio.TimeoutError:
                continue

            if raw is None:
                break

            msg   = json.loads(raw)
            event = msg.get("event")

            # ── Stream démarré ────────────────────────────────────────────────
            if event == "start":
                stream_sid = msg["start"]["streamSid"]
                print(f"[TWILIO] Stream : {stream_sid}")
                # Salutation : attente bloquante (pas de barge-in sur la 1ère phrase)
                await _play_tts_blocking("9-1-1, what's your emergency?")
                print("[TWILIO] Salutation envoyée.")

            # ── Chunk audio entrant ───────────────────────────────────────────
            elif event == "media":
                track = msg["media"].get("track", "inbound")
                if track in ("outbound", "outbound_track"):
                    continue

                mulaw     = base64.b64decode(msg["media"]["payload"])
                pcm_chunk = audioop.ulaw2lin(mulaw, 2)
                rms       = float(np.sqrt(np.mean(
                    np.frombuffer(pcm_chunk, np.int16).astype(np.float32) ** 2
                )))

                # Pendant le TTS : ignorer tout l'audio entrant (pas de barge-in)
                if agent_speaking:
                    continue

                # TTS vient de terminer → nettoyer
                if tts_task and tts_task.done():
                    tts_task = None

                # VAD normal
                if rms > SPEECH_THRESH:
                    recording     = True
                    silence_count = 0
                    speech_count += 1
                    pcm_buffer.extend(pcm_chunk)

                elif recording:
                    silence_count += 1
                    pcm_buffer.extend(pcm_chunk)

                    if silence_count >= SILENCE_CHUNKS and speech_count >= MIN_SPEECH:
                        audio_data = bytes(pcm_buffer)
                        _reset_vad()

                        # Transcription + analyse vocale (en parallèle)
                        text, voice_emo = await asyncio.gather(
                            loop.run_in_executor(None, transcribe_pcm, audio_data),
                            loop.run_in_executor(None, analyze_voice_emotion, audio_data),
                        )
                        if not text:
                            continue
                        print(f"[TWILIO] Caller: '{text}'")

                        # Mise à jour émotion vocale
                        if voice_emo:
                            print(f"[VOICE EMO] {voice_emo['emoji']} {voice_emo['label']} ({voice_emo['confidence']:.2f})")
                            cur = get_call(call_id) or {}
                            history = cur.get("voice_emotion_history", [])[-( MAX_HISTORY - 1):]
                            history.append(voice_emo)
                            update_call(call_id, {
                                "voice_emotion":         voice_emo,
                                "voice_emotion_history": history,
                            })

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
                        update_call(call_id, {"transcript": agent.get_transcript()})
                        await manager.broadcast({"event": "db_response", "data": get_all_calls()})

                        # ── TTS (background → barge-in possible) ─────────────
                        if response_text and stream_sid:
                            await _play_tts_background(response_text)

                        # ── Détection fin d'appel par l'agent ─────────────────
                        if response_text and "goodbye" in response_text.lower():
                            await asyncio.sleep(2.0)
                            close_event.set()

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

                                    call_type = extracted.get("type") or get_call(call_id).get("type")
                                    coords    = geo.get("coordinates")
                                    if coords and agent_module.EMERGENCY_REGISTRY:
                                        nearest = find_nearest(
                                            coords["lat"], coords["lng"],
                                            call_type, agent_module.EMERGENCY_REGISTRY
                                        )
                                        if nearest:
                                            try:
                                                route = await asyncio.wait_for(
                                                    loop.run_in_executor(None, get_route,
                                                        nearest["lat"], nearest["lng"],
                                                        coords["lat"], coords["lng"]),
                                                    timeout=25.0,
                                                )
                                            except (asyncio.TimeoutError, Exception):
                                                route = None
                                            nearest["route"] = route
                                            update_call(call_id, {"nearest_service": nearest})

                                            if not dispatch_sent:
                                                dispatch_sent = True
                                                dispatch_text = await agent.generate_dispatch_message(nearest)
                                                agent.standard_transcript.append(
                                                    {"role": "assistant", "content": dispatch_text}
                                                )
                                                update_call(call_id, {"transcript": agent.get_transcript()})
                                                # Attendre que le TTS de la réponse précédente soit terminé
                                                if tts_task and not tts_task.done():
                                                    try:
                                                        await tts_task
                                                    except Exception:
                                                        pass
                                                await _play_tts_background(dispatch_text)

                            await manager.broadcast({"event": "db_response", "data": get_all_calls()})

            # ── Fin du stream ─────────────────────────────────────────────────
            elif event == "stop":
                print(f"[TWILIO] Appel terminé — {call_id}")
                break

    except (WebSocketDisconnect, Exception) as e:
        print(f"[TWILIO] Déconnexion : {e}")
    finally:
        active_streams.pop(call_id, None)
        recv_task.cancel()
        await _interrupt()
        update_call(call_id, {"status": "ended"})
        await manager.broadcast({"event": "db_response", "data": get_all_calls()})
        print(f"[TWILIO] Stream fermé — {call_id}")
        # Envoyer le résumé par SMS (attendu pour garantir l'envoi avant fermeture)
        call_data = get_call(call_id)
        if call_data:
            try:
                await loop.run_in_executor(None, send_call_summary_sms, call_data)
            except Exception as e:
                print(f"[SMS] Erreur finale : {e}")
