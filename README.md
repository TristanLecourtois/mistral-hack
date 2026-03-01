
# Mistral Hack Backend Service

This directory contains the backend service and supporting assets for the Mistral Hackathon project. The service is built using Python and provides APIs for speech-to-text, text-to-speech, emergency lookups, geocoding, and more.

The idea is to handle large incoming call volumes during a catastrophic event when call centers are overwhelmed. The goal is not to replace human responders, but to provide a solution for managing localized, high-volume calls that come in at once for the same event.

Mistral-7B Fine-tuning with LoRA + Weave Score regularization term during training.


## 🗂️ Repository Structure

```
mistral-hack/
├── backend/                      # Core Python service modules
│   ├── __init__.py
│   ├── agent.py                  # Main agent logic
│   ├── db.py                     # Database interactions
│   ├── emergency_services.py     # Emergency lookup utilities
│   ├── geocoding.py              # Geocoding helpers
│   ├── main.py                   # Entry point for running the service
│   ├── prompts.py                # Prompt templates for AI models
│   ├── socket_manager.py         # Websocket handling
│   ├── stt.py                    # Speech-to-text endpoints
│   ├── tts.py                    # Text-to-speech endpoints
│   ├── twilio_voice.py           # Twilio integration for voice calls
│   └── test.py                   # Miscellaneous tests/examples
│   └── services/                 # External third‑party service wrappers
│       ├── elevenlabs_tts.py
│       ├── emotion_nlp.py
│       └── voxtral_asr.py
├── data/                         # Static data assets
│   └── police.json               # Example emergency data file
├── frontend/                     # Simple demo web client
│   ├── app.js
│   ├── index.html
│   └── style.css
├── notebooks/                    # Development notebooks (empty placeholder)
│   └── .gitkeep
└── utils/                        # Shared utility modules
    ├── helpers.py
    └── logging.py

Additional top-level files:
- `.gitignore`
- `pyproject.toml`                # project metadata and dependencies
- `requirements.txt`             # Python dependencies

```

## 🚀 Getting Started

1. **Create & activate a virtual environment**
   ```bash
   python -m venv venv
   source venv/bin/activate   # macOS/Linux
   venv\\Scripts\\activate    # Windows
   ```
2. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```
3. **Configure environment variables**
   Set keys such as `MISTRAL_API_KEY`, `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`, etc.
   You can use a `.env` file and load it at startup.
4. **Run the service**
   ```bash
   python backend/main.py
   ```
   The API will start on the configured host/port (default `localhost:8000`).

## 🛠 Key Features

- **Speech-to-Text (STT)** via Mistral Voxtral
- **Text-to-Speech (TTS)** through ElevenLabs or other providers
- **Emergency services lookup** using static data and geocoding
- **Twilio voice call handling** for interactive sessions
- **Websocket support** for realtime communication

## 📦 Dependencies

Managed in `requirements.txt`. Core libraries include fastapi/Flask (depending on implementation), requests, and AI client SDKs.

## 🎯 Usage Examples

- Start a transcription session via the STT endpoint
- Convert text to speech using the TTS route
- Request emergency information based on a location
- Use the frontend in `frontend/` for a simple UI demo

## 🧪 Testing

The `backend/test.py` file contains small snippets for manual testing. Extend as needed.

## 🤝 Contributing

Contributions are welcome! Fork the repository, make changes, and submit a pull request. Document any new endpoints or features.

---

*This README is focused solely on the contents of the `mistral-hack` backend service.*
