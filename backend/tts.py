import os
import requests
from dotenv import load_dotenv

load_dotenv()

ELEVENLABS_KEY = os.getenv("ELEVENLABS_API_KEY", "")
VOICE_ID       = os.getenv("ELEVENLABS_VOICE_ID", "EXAVITQu4vr4xnSDxMaL")  # Sarah


def speak_pcm(text: str) -> bytes:
    """
    Convertit du texte en audio PCM 16-bit 8kHz via ElevenLabs.
    Retourne directement les bytes PCM — pas besoin de convertir depuis MP3.
    """
    if not ELEVENLABS_KEY:
        raise RuntimeError("ELEVENLABS_API_KEY manquant dans .env")

    resp = requests.post(
        f"https://api.elevenlabs.io/v1/text-to-speech/{VOICE_ID}"
        f"?output_format=pcm_8000",
        headers={
            "xi-api-key": ELEVENLABS_KEY,
            "Content-Type": "application/json",
        },
        json={
            "text": text,
            "model_id": "eleven_turbo_v2_5",
            "voice_settings": {
                "stability": 0.45,
                "similarity_boost": 0.80,
                "speed": 1.05,
            },
        },
        timeout=20,
    )
    resp.raise_for_status()
    return resp.content  # PCM 8kHz, 16-bit, mono
