import os
from twilio.rest import Client
from dotenv import load_dotenv

load_dotenv()

_FALLBACK = {
    "fire": (
        "1. Leave the building NOW - do not use the elevator\n"
        "2. Close every door behind you to slow the fire\n"
        "3. Stay low if there is smoke - crawl if needed\n"
        "4. Wait for firefighters outside, do not go back in"
    ),
    "hospital": (
        "1. Stay calm and breathe slowly\n"
        "2. Do not move the injured person\n"
        "3. Press firmly on any bleeding wound\n"
        "4. Keep them warm and still until help arrives"
    ),
    "police": (
        "1. Stay calm - do not confront anyone\n"
        "2. Lock doors and move away from windows\n"
        "3. Keep your phone on silent\n"
        "4. Do not open the door until officers identify themselves"
    ),
    "other": (
        "1. Stay calm and stay where you are\n"
        "2. Do not put yourself in further danger\n"
        "3. Follow dispatcher instructions\n"
        "4. Help is on the way"
    ),
}


def send_call_summary_sms(call: dict):
    account_sid = os.getenv("TWILIO_ACCOUNT_SID", "")
    auth_token  = os.getenv("TWILIO_AUTH_TOKEN", "")
    from_number = os.getenv("TWILIO_PHONE_NUMBER", "")
    to_number   = os.getenv("OPERATOR_PHONE", "")

    if not all([account_sid, auth_token, from_number, to_number]):
        print("[SMS] Credentials manquants — SMS non envoyé")
        return

    call_type = call.get("type") or "other"
    severity  = call.get("severity", "UNKNOWN")
    location  = call.get("location_name", "Unknown location")

    # Instructions extraites pendant l'appel (liste ou string), sinon fallback statique
    raw_instr = call.get("instructions")
    if isinstance(raw_instr, list):
        instructions = "\n".join(f"{i+1}. {s}" for i, s in enumerate(raw_instr))
    elif isinstance(raw_instr, str) and raw_instr.strip():
        instructions = raw_instr
    else:
        instructions = _FALLBACK.get(call_type, _FALLBACK["other"])

    body = (
        f"[911] {severity} {call_type.upper()}\n"
        f"{location}\n"
        f"---\n"
        f"{instructions}"
    )

    try:
        client = Client(account_sid, auth_token)
        msg = client.messages.create(body=body, from_=from_number, to=to_number)
        print(f"[SMS] Envoyé → {to_number} | SID={msg.sid} | status={msg.status}")
    except Exception as e:
        print(f"[SMS] Erreur : {e}")
