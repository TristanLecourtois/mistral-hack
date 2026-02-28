import io
import os
import wave
import requests
from dotenv import load_dotenv

load_dotenv()


def _pcm_to_wav(pcm_bytes: bytes, sample_rate: int = 8000) -> bytes:
    """Encode des bytes PCM 16-bit mono en WAV en mémoire."""
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)   # 16-bit
        wf.setframerate(sample_rate)
        wf.writeframes(pcm_bytes)
    return buf.getvalue()


def transcribe_pcm(pcm_bytes: bytes, sample_rate: int = 8000) -> str:
    """
    Transcrit des bytes PCM 16-bit mono en texte via Mistral Voxtral.
    """
    wav_bytes = _pcm_to_wav(pcm_bytes, sample_rate)
    api_key = os.getenv("MISTRAL_API_KEY", "")

    resp = requests.post(
        "https://api.mistral.ai/v1/audio/transcriptions",
        headers={"Authorization": f"Bearer {api_key}"},
        files={"file": ("audio.wav", wav_bytes, "audio/wav")},
        data={"model": "voxtral-mini-2507"},
        timeout=30,
    )
    resp.raise_for_status()

    text = resp.json().get("text", "").strip()
    if text:
        print(f"[STT] '{text}'")
    return text
