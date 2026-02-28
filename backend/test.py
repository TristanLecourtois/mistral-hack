import asyncio
import websockets
import json


async def recv_until_end(websocket) -> str:
    """Lit les chunks jusqu'à assistant_end et retourne le texte complet."""
    text = ""
    while True:
        raw = await websocket.recv()
        msg = json.loads(raw)
        if msg["type"] == "assistant_input":
            print(msg["text"], end="", flush=True)
            text += msg["text"]
        elif msg["type"] == "assistant_end":
            print()
            break
        elif msg["type"] == "assistant_error":
            print(f"\n[ERREUR] {msg['text']}")
            break
    return text


async def test():
    uri = "ws://127.0.0.1:8000/voxtral"
    conversation = []
    loop = asyncio.get_event_loop()

    async with websockets.connect(uri, ping_interval=None) as websocket:
        print("Connecté au dispatcher 911. Tape 'quit' pour quitter.\n")

        # Lire le greeting initial AVANT de demander l'input
        print("Dispatcher: ", end="", flush=True)
        greeting = await recv_until_end(websocket)
        if greeting:
            conversation.append({"message": {"role": "assistant", "content": greeting}})

        # Boucle de conversation
        while True:
            user_input = (await loop.run_in_executor(None, input, "Vous: ")).strip()
            if user_input.lower() == "quit":
                break
            if not user_input:
                continue

            conversation.append({"message": {"role": "user", "content": user_input}})
            await websocket.send(json.dumps({"messages": conversation}))

            print("Dispatcher: ", end="", flush=True)
            assistant_text = await recv_until_end(websocket)

            if assistant_text:
                conversation.append({"message": {"role": "assistant", "content": assistant_text}})


asyncio.run(test())
