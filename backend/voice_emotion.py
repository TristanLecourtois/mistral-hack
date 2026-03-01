"""
Analyse de l'émotion vocale via SpeechBrain wav2vec2 (IEMOCAP).

Modèle : speechbrain/emotion-recognition-wav2vec2-IEMOCAP
Classes : neu (neutral), hap (happy), sad (sad), ang (angry)

L'audio Twilio arrive en PCM 16-bit mono 8 kHz.
On le rééchantillonne à 16 kHz avant de l'envoyer au modèle.
"""

import os
import wave
import audioop
import tempfile
import warnings
from typing import Optional

# Supprimer les warnings non-critiques de SpeechBrain / torchaudio
warnings.filterwarnings("ignore", category=UserWarning, module="speechbrain")
warnings.filterwarnings("ignore", category=UserWarning, module="torchaudio")
warnings.filterwarnings("ignore", category=UserWarning, module="transformers")

_classifier = None

# Dans le contexte d'un appel d'urgence, les classes IEMOCAP sont reinterprétées :
#   neu → Composé   (appelant calme, maîtrise la situation)
#   hap → Agité     (énergie élevée / adrénaline / état de choc)
#   sad → En détresse (voix brisée, abattement)
#   ang → Paniqué   (urgence extrême, cris, stress intense)
EMOTION_MAP = {
    "neu": {"label": "Composed",   "emoji": "🫤", "color": "#94a3b8"},
    "hap": {"label": "Agitated",   "emoji": "😬", "color": "#fb923c"},
    "sad": {"label": "Distressed", "emoji": "😟", "color": "#60a5fa"},
    "ang": {"label": "Panicked",   "emoji": "😤", "color": "#f43f5e"},
}

DEFAULT_EMOTION = {
    "code":       "neu",
    "label":      EMOTION_MAP["neu"]["label"],
    "emoji":      EMOTION_MAP["neu"]["emoji"],
    "color":      EMOTION_MAP["neu"]["color"],
    "confidence": None,
}

MAX_HISTORY = 10  # nombre max d'entrées conservées dans l'historique


def _get_classifier():
    global _classifier
    if _classifier is None:
        print("[VOICE EMO] Chargement du modèle SpeechBrain…")
        from speechbrain.inference.interfaces import foreign_class
        _classifier = foreign_class(
            source="speechbrain/emotion-recognition-wav2vec2-IEMOCAP",
            pymodule_file="custom_interface.py",
            classname="CustomEncoderWav2vec2Classifier",
        )
        print("[VOICE EMO] Modèle prêt.")
    return _classifier


def analyze_voice_emotion(pcm_8k: bytes) -> Optional[dict]:
    """
    Analyse l'émotion d'un segment audio PCM 16-bit mono 8 kHz.
    Retourne un dict {code, label, emoji, color, score} ou None en cas d'erreur.
    """
    try:
        # Rééchantillonnage 8 kHz → 16 kHz (audioop, pas de dépendance lourde)
        pcm_16k, _ = audioop.ratecv(pcm_8k, 2, 1, 8000, 16000, None)

        # Fichier WAV temporaire attendu par SpeechBrain
        tmp_fd, tmp_path = tempfile.mkstemp(suffix=".wav")
        os.close(tmp_fd)
        try:
            with wave.open(tmp_path, "wb") as wf:
                wf.setnchannels(1)
                wf.setsampwidth(2)
                wf.setframerate(16000)
                wf.writeframes(pcm_16k)

            clf = _get_classifier()
            _, score, _, text_lab = clf.classify_file(tmp_path)
        finally:
            os.unlink(tmp_path)

        code = text_lab[0]  # "neu" | "hap" | "sad" | "ang"
        info = EMOTION_MAP.get(code, EMOTION_MAP["neu"])

        raw_score = score
        if hasattr(raw_score, "item"):
            raw_score = raw_score.item()
        confidence = round(float(raw_score), 3)

        return {
            "code":       code,
            "label":      info["label"],
            "emoji":      info["emoji"],
            "color":      info["color"],
            "confidence": confidence,
        }

    except Exception as e:
        print(f"[VOICE EMO] Erreur : {e}")
        return None
