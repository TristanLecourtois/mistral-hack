# Mistral Hackathon Project

This repository contains a collection of scripts and a backend service developed for a hackathon project combining real-time speech transcription, Twilio voice calls, Discord audio capture, and AI assistants powered by Mistral.

## 📁 Repository Structure

```
├── call_handler.py          # Twilio call handling logic
├── discord_transcriptions.json
├── disttt.py                # Discord audio capture and realtime transcription example
├── env.py                   # Environment variables (API keys) for local testing
├── json_writer.py           # Utility for writing JSON logs
├── req.txt                  # Requirements file for main scripts
├── requirements.txt         # Primary Python dependencies
├── send_call.py             # Example of initiating Twilio call
├── session_store.py         # Manages storage of active sessions
├── stream_manager.py        # Audio stream management utilities
├── test.py                  # Misc tests/examples
├── tt.py                    # Text-to-speech or transcription helper
├── voxtral_client.py        # Wrapper around Mistral Voxtral API
├── mistral-hack/            # Backend service subproject
│   ├── backend/             # Flask/FastAPI service files
│   │   ├── agent.py
│   │   ├── db.py
│   │   ├── emergency_services.py
│   │   ├── geocoding.py
│   │   ├── main.py
│   │   ├── prompts.py
│   │   ├── socket_manager.py
│   │   ├── stt.py
│   │   ├── tts.py
│   │   ├── twilio_voice.py
│   │   └── services/         # External integrations (ElevenLabs, emotion NLP, voxtral ASR)
│   ├── data/                 # Static assets like `police.json`
│   ├── frontend/             # Simple web UI assets
│   ├── notebooks/            # Development notebooks
│   └── utils/                # Shared helper modules
└── speech-assistant-openai-realtime-api-python/  # Example realtime API client
```

## 🚀 Getting Started

### 1. Clone the repository

```bash
git clone <repo-url> mistral-hackaton
cd mistral-hackaton
```

### 2. Install Python dependencies

```bash
python -m venv venv
venv\Scripts\activate      # Windows
pip install -r requirements.txt
# For the subproject:
pip install -r mistral-hack/requirements.txt
```

### 3. Configuration

Create a `.env` file or modify `env.py` with required API keys:

```
MISTRAL_API_KEY=your_key_here
TWILIO_ACCOUNT_SID=...
TWILIO_AUTH_TOKEN=...
DISCORD_TOKEN=...
```

> **Note:** `env.py` currently contains placeholder keys only used for local testing. Avoid committing real keys.

### 4. Running components

- **Twilio call handling**: `python call_handler.py`
- **Initiate a call**: `python send_call.py`
- **Discord transcription demo**: `python disttt.py`
- **Backend service**:
  1. `cd mistral-hack/backend`
  2. `python main.py`
  3. The API exposes endpoints for STT/ TTS, emergency services, etc.

### 5. Development notebooks

The `notebooks` directories contain exploratory work. Open them with JupyterLab/Notebook:

```bash
jupyter notebook
```

## 🛠 Key Features

- **Real-time speech transcription** using Mistral Voxtral
- **Twilio voice call integration** for interactive assistants
- **Discord audio capture** for group transcriptions
- **Backend API** supporting geocoding, emergency lookups, emotion analysis, and more
- **Frontend demo** demonstrating simple UI usage

## 📌 Notes & Tips

- The project is experimental and built for hackathon demo purposes.
- Ensure all API credentials are kept private and not checked into version control.
- Many scripts log output to JSON for analysis (`discord_transcriptions.json`, etc.).

## 👩‍💻 Contributing

Feel free to branch and open pull requests. Provide clear descriptions and run existing tests where applicable.

## 📄 Licensing

See individual `LICENSE` files. The downstream subproject follows its own licensing terms.

---

Happy hacking! 🎉
