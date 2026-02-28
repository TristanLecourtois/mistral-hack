voice_assistant_hackathon/
│
├─ README.md                   # Description, setup, instructions
├─ .env                        # Clés API : Voxtral, ElevenLabs, Google Maps
├─ requirements.txt            # Dépendances Python
├─ pyproject.toml / setup.py   # Optionnel si packaging
│
├─ server/                     # Backend (FastAPI + WebSocket)
│   ├─ __init__.py
│   ├─ main.py                 # Lancement FastAPI / WebSocket
│   ├─ socket_manager.py       # Gestion broadcast / clients WebSocket
│   ├─ db.py                   # CRUD pour stockage des appels / transcripts
│   ├─ geocoding.py            # Google Maps API : geocode / street view
│   ├─ prompts.py              # SYSTEM_PROMPT et templates LLM
│   ├─ voice_agent.py          # Agent principal : LLM, history, gestion émotions
│   ├─ services/               # Services externes
│   │   ├─ voxtral_asr.py      # Transcription audio → texte
│   │   ├─ elevenlabs_tts.py   # Génération audio réponse
│   │   └─ emotion_nlp.py      # Analyse émotionnelle texte (GPT ou ML)
│   └─ evals.py                # Fonctions évaluation / scoring (ancien eval.py)
│
├─ frontend/                   # Client Web (optionnel, peut être JS ou React)
│   ├─ index.html
│   ├─ app.js                  # WebSocket connect, audio capture, playback
│   └─ style.css
│
├─ notebooks/                  # Exploration, tests API ElevenLabs / Voxtral
│
└─ utils/                      # Scripts utilitaires
    ├─ logging.py
    └─ helpers.py