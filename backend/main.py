import json
import uuid
from contextlib import asynccontextmanager
from datetime import datetime
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from socket_manager import manager
from db import get_all_calls, get_call, update_call
from emergency_services import build_registry
import agent as agent_module
import twilio_voice


@asynccontextmanager
async def lifespan(app):
    # Chargement des services d'urgence au démarrage (une seule fois)
    import asyncio
    print("[STARTUP] Chargement des services d'urgence...")
    agent_module.EMERGENCY_REGISTRY = await asyncio.get_event_loop().run_in_executor(
        None, build_registry
    )
    print("[STARTUP] Services chargés.")
    yield


app = FastAPI(lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(agent_module.router)
app.include_router(twilio_voice.router)

# Sert les fichiers du frontend
app.mount("/static", StaticFiles(directory="../frontend"), name="static")


@app.get("/")
async def root():
    return {"status": "Server running"}


@app.websocket("/dashboard")
async def dashboard_endpoint(websocket: WebSocket):
    client_id = str(uuid.uuid4())
    await manager.connect(websocket, client_id)
    try:
        # Envoie l'état actuel immédiatement à la connexion
        await manager.send_personal_message(
            {"event": "db_response", "data": get_all_calls()}, websocket
        )
        while True:
            raw = await websocket.receive_text()
            try:
                msg = json.loads(raw)
                if msg.get("type") == "dispatch":
                    _handle_dispatch(msg)
                    await manager.broadcast({"event": "db_response", "data": get_all_calls()})
            except Exception:
                pass  # keepalive ou message non-JSON
    except WebSocketDisconnect:
        await manager.disconnect(client_id)


def _handle_dispatch(msg: dict):
    call_id = msg.get("call_id")
    service = msg.get("service")  # "police" | "fire" | "hospital"
    if not call_id or not service:
        return
    call = get_call(call_id)
    if not call:
        return
    dispatched = list(call.get("dispatched_to", []))
    if service not in dispatched:
        dispatched.append(service)
    update_call(call_id, {
        "dispatched_to": dispatched,
        f"dispatched_{service}_at": datetime.now().isoformat(),
    })
    print(f"[DISPATCH] {service.upper()} → appel {call_id}")
