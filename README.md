
# AuxilAI

**AuxilAI** is an AI-powered 911 emergency dispatch system designed to handle massive incoming call volumes during catastrophic events — fires, accidents, medical emergencies, criminal incidents — when human call centers are overwhelmed.

The system acts as an intelligent first responder: it answers emergency calls in real time (via phone or browser), gathers critical information through natural conversation, geolocates the incident, identifies the nearest emergency service, calculates the optimal route, and dispatches the right responders — all automatically, in seconds.

> **AuxilAI does not replace human dispatchers.** It is built to handle localized, high-volume call surges so that human operators can focus on the most complex situations.

---

<video src="demo/demo_mistral_hack.mp4" controls width="100%"></video>

---

## 🏗️ Technical Architecture

```
╔══════════════════════════════════════════════════════════════════════════════════════╗
║                              SOURCES D'APPELS                                        ║
╠═══════════════════════════╦════════════════════════════════════════════════════════  ║
║   📞 APPEL TÉLÉPHONIQUE   ║             🌐 INTERFACE WEB (Voxtral)                   ║
║       (Twilio PSTN)       ║                 (Browser)                                ║
╚═══════════════════════════╩════════════════════════════════════════════════════════╝
          │                                        │
          │ 1. POST /twilio/incoming               │ WebSocket ws://backend/voxtral
          │    → TwiML <Stream url="wss://...">    │ (messages JSON {type, messages[]})
          ▼                                        ▼
╔═══════════════════════════════════════════════════════════════════════════════════════╗
║                          BACKEND FastAPI  (backend/main.py)                          ║
║  ┌─────────────────────────────────────────────────────────────────────────────┐     ║
║  │                         STARTUP / LIFESPAN                                  │     ║
║  │  build_registry() → police.json + Overpass OSM (fire + hospitals)           │     ║
║  │  find_nearest() + get_route() pré-calculés pour les appels existants        │     ║
║  └─────────────────────────────────────────────────────────────────────────────┘     ║
║                                                                                       ║
║  ┌─────────────────────────┐    ┌─────────────────────────┐   ┌──────────────────┐   ║
║  │   /twilio/stream (WS)   │    │    /voxtral (WS)         │   │  /dashboard (WS) │   ║
║  │  twilio_voice.py        │    │    agent.py              │   │  main.py         │   ║
║  └────────────┬────────────┘    └──────────┬──────────────┘   └───────┬──────────┘   ║
║               │                            │                           │               ║
╚═══════════════╪════════════════════════════╪═══════════════════════════╪═══════════════╝
                │                            │                           │
                ▼                            ▼                           ▼
╔══════════════════════════════════╗  ╔════════════════════╗  ╔═══════════════════════╗
║    PIPELINE AUDIO (Twilio)       ║  ║   PIPELINE TEXTE   ║  ║  DASHBOARD FRONTEND  ║
║                                  ║  ║   (Voxtral)        ║  ║  frontend/index.html ║
║  Twilio mulaw 8kHz (base64)      ║  ║                    ║  ║  frontend/app.js     ║
║  → audioop.ulaw2lin() → PCM      ║  ║  parse_voxtral_    ║  ║                      ║
║                                  ║  ║  message()         ║  ║  ┌────────────────┐  ║
║  ┌─────────────────────────────┐ ║  ╚════════════════════╝  ║  │  Sidebar Left  │  ║
║  │      VAD (RMS Energy)       │ ║           │              ║  │  call list     │  ║
║  │  SPEECH_THRESH = 400 RMS    │ ║           │              ║  │  stats         │  ║
║  │  MIN_SPEECH = 300ms         │ ║           ▼              ║  └────────────────┘  ║
║  │  SILENCE = 500ms            │ ║  ╔════════════════════╗  ║  ┌────────────────┐  ║
║  └────────────┬────────────────┘ ║  ║    Agent (AI)       ║  ║  │  Map (Leaflet) │  ║
║               │ speech detected  ║  ║   agent.py          ║  ║  │  markers       │  ║
║               ▼                  ║  ║   ministral-8b      ║  ║  │  routes        │  ║
║  ┌────────────────────────────┐  ╚══╬════════════════════╬╝  ║  │  dispatch panel│  ║
║  │    STT (Transcription)     │     ║                    ║   ║  └────────────────┘  ║
║  │    stt.py                  │     ║  get_responses()   ║   ║  ┌────────────────┐  ║
║  │  PCM → WAV → HTTP POST     │─────►  (streaming)      ║   ║  │ Sidebar Right  │  ║
║  │  Mistral voxtral-mini-2507 │     ║  → yield chunks   ║   ║  │ transcript     │  ║
║  └────────────────────────────┘     ╚═════════╦══════════╝   ║  │ emotions       │  ║
║                                               │              ║  │ scores (radar) │  ║
║  ┌────────────────────────────────────────────▼────────────┐ ║  │ street view    │  ║
║  │                  PIPELINE TTS STREAMING                  │ ║  └────────────────┘  ║
║  │  sentence split (_SENT_RE) → phrases                     │ ║                      ║
║  │  run_in_executor(speak_pcm, phrase) ← parallèle          │ ║  WebSocket           ║
║  │    TTS : ElevenLabs eleven_turbo_v2_5                    │ ║  ws://backend/       ║
║  │         tts.py  → PCM 8kHz direct                        │ ║  dashboard           ║
║  │  pcm_to_mulaw_chunks() → base64 → Twilio WS              │ ║                      ║
║  │                                                           │ ╚═══════════════════════╝
║  │  ⚡ BARGE-IN : barge_flag[0]=True → stop immédiat        │
║  └──────────────────────────────────────────────────────────┘
╚══════════════════════════════════════════════════════════════╝

                              │  Après chaque réponse
                              ▼
╔═══════════════════════════════════════════════════════════════════════════════════════╗
║                       PIPELINE D'EXTRACTION & GÉOLOCALISATION                         ║
║                                                                                       ║
║   ┌───────────────────────────────┐                                                   ║
║   │    extract_call_info()        │  Mistral ministral-8b (EXTRACTION_PROMPT)         ║
║   │    → JSON structuré :         │  temperature=0.1, non-streaming                   ║
║   │      title, summary, severity │                                                   ║
║   │      type (fire/police/hosp.) │                                                   ║
║   │      location_name            │                                                   ║
║   │      emotions[], scores{}     │                                                   ║
║   │      instructions[]           │                                                   ║
║   └───────────────┬───────────────┘                                                   ║
║                   │ si location_name nouveau                                           ║
║                   ▼                                                                   ║
║   ┌───────────────────────────────┐     ┌───────────────────────────────────────────┐ ║
║   │    geocode_location()         │     │           find_nearest()                  │ ║
║   │    geocoding.py               │────►│           emergency_services.py           │ ║
║   │    Google Maps Geocoding API  │     │   Haversine distance → type matching      │ ║
║   │    → lat, lng                 │     │   Registry: police / fire / hospital      │ ║
║   │    → formatted_address        │     └─────────────────┬─────────────────────────┘ ║
║   │    → Street View URL          │                       │                           ║
║   └───────────────────────────────┘                       ▼                           ║
║                                           ┌───────────────────────────────────────┐   ║
║                                           │           get_route()                  │   ║
║                                           │   OSRM (router.project-osrm.org)      │   ║
║                                           │   → Valhalla (openstreetmap.de) fallback│  ║
║                                           │   → [[lat,lng], ...] polyline          │   ║
║                                           └───────────────┬───────────────────────┘   ║
║                                                           │                           ║
║                                                           ▼                           ║
║                                           ┌───────────────────────────────────────┐   ║
║                                           │    generate_dispatch_message()         │   ║
║                                           │    Mistral → phrase de dispatch        │   ║
║                                           │    → TTS → audio caller               │   ║
║                                           └───────────────────────────────────────┘   ║
╚═══════════════════════════════════════════════════════════════════════════════════════╝

                              │  Fin d'appel ("Goodbye" ou dashboard)
                              ▼
╔═══════════════════════════════════════════╗
║         POST-CALL ACTIONS                 ║
║                                           ║
║  send_call_summary_sms()  sms.py          ║
║  Twilio SMS → OPERATOR_PHONE              ║
║  [severity, type, location, instructions] ║
╚═══════════════════════════════════════════╝

╔═══════════════════════════════════════════════════════════════╗
║              IN-MEMORY DATABASE  (db.py)                      ║
║                                                               ║
║  calls_db: dict[call_id → call_object]                        ║
║  call_object: {                                               ║
║    id, mode, time, status, transcript[],                      ║
║    type, severity, title, summary,                            ║
║    name, phone, location_name,                                ║
║    coordinates {lat, lng},                                    ║
║    street_image (Google Street View URL),                     ║
║    emotions[], scores{}, recommendation,                      ║
║    nearest_service {name, type, distance_km, route},          ║
║    dispatched_to[], dispatched_*_at                           ║
║  }                                                            ║
║  Initialisé avec 7 appels fictifs au démarrage                ║
╚═══════════════════════════════════════════════════════════════╝

╔═══════════════════════════════════════════════════════════════╗
║           SOCKET MANAGER  (socket_manager.py)                 ║
║                                                               ║
║  ConnectionManager: active_connections{client_id → WS}        ║
║  broadcast(data) → envoie à tous les dashboards connectés     ║
║  → déclenché par : nouvelle utterance, extraction, geocode,   ║
║    nearest_service, dispatch, fin d'appel                     ║
╚═══════════════════════════════════════════════════════════════╝

╔═══════════════════════════════════════════════════════════════════════════════════╗
║                         ANALYSE VOCALE  (voice_emotion.py)                        ║
║                                                                                   ║
║  SpeechBrain wav2vec2-IEMOCAP                                                     ║
║  PCM 8kHz → audioop.ratecv → 16kHz WAV → classify_file()                         ║
║  Classes : neu→Composed 🫤 | hap→Agitated 😬 | sad→Distressed 😟 | ang→Panicked 😤  ║
╚═══════════════════════════════════════════════════════════════════════════════════╝

╔══════════════════════════════════════════════════════════════════════════╗
║               DONNÉES & REGISTRE D'URGENCES                              ║
║                                                                          ║
║  data/police.json   → commissariats parisiens (coords WGS84)             ║
║  OSM Overpass API   → casernes pompiers (bbox Paris 48.70-49.00,2.20-2.60)║
║  OSM Overpass API   → hôpitaux (même bbox)                               ║
║  EMERGENCY_REGISTRY = { "police": [...], "fire": [...], "hospital": [...]}║
║  Chargé UNE SEULE FOIS au startup, partagé via agent_module.             ║
╚══════════════════════════════════════════════════════════════════════════╝

╔══════════════════════════════════════════════════════════════════════════╗
║              ML / FINE-TUNING (hors production)                          ║
║                                                                          ║
║  data_gen/data_gen.py     → génération de dataset via Mistral            ║
║  dataset/                 → 2000 samples JSON (train/test split)         ║
║  fine_tuning/             → HuggingFace fine-tune + W&B tracking         ║
║  test_depoly/             → test déploiement SageMaker                   ║
╚══════════════════════════════════════════════════════════════════════════╝
```

### Call flows

**Real phone call (Twilio)**
```
Caller → PSTN → Twilio → POST /twilio/incoming
  → TwiML <Stream url="wss://backend/twilio/stream">
  → WS /twilio/stream (mulaw 8kHz, 20ms chunks)
  → VAD (RMS > 400) → PCM buffer
  → 500ms silence → STT: Mistral voxtral-mini-2507
  → text → Agent: ministral-8b streaming
  → complete sentence → TTS: ElevenLabs eleven_turbo_v2_5 (PCM 8kHz)
  → mulaw → Twilio → Caller
  → extract_call_info() → geocode() → find_nearest() → get_route()
  → broadcast() → Dashboard
  → call end → SMS summary → operator
```

**Dashboard (real-time)**
```
Dashboard WS /dashboard
  ← broadcast({event: "db_response", data: all_calls})
  → click dispatch → ws.send({type:"dispatch", call_id, service})
  → backend _handle_dispatch() → update_call() → broadcast()
```

### External services

| Service | Usage | Module |
|---|---|---|
| **Mistral `ministral-8b-latest`** | Dispatcher AI chat (streaming) | `agent.py` |
| **Mistral `voxtral-mini-2507`** | Speech-to-text transcription | `stt.py` |
| **ElevenLabs `eleven_turbo_v2_5`** | Text-to-speech (Sarah voice) | `tts.py` |
| **Twilio** | Telephony + SMS | `twilio_voice.py`, `sms.py` |
| **Google Maps** | Geocoding + Street View | `geocoding.py` |
| **OSM Overpass API** | Fire stations + hospitals lookup | `emergency_services.py` |
| **OSRM / Valhalla** | Real route calculation | `emergency_services.py` |
| **SpeechBrain wav2vec2** | Vocal emotion analysis | `voice_emotion.py` |

---

## 🗂️ Repository Structure

```
mistral-hack/
├── backend/                      # Core Python service modules
│   ├── main.py                   # FastAPI entry point, lifespan startup
│   ├── agent.py                  # AI Agent (Mistral), WebSocket /voxtral
│   ├── twilio_voice.py           # Twilio telephony integration
│   ├── socket_manager.py         # WebSocket broadcast manager
│   ├── db.py                     # In-memory calls database
│   ├── prompts.py                # System + extraction prompts
│   ├── stt.py                    # Speech-to-text (Mistral Voxtral)
│   ├── tts.py                    # Text-to-speech (ElevenLabs)
│   ├── sms.py                    # Post-call SMS summary (Twilio)
│   ├── geocoding.py              # Google Maps geocoding + Street View
│   ├── emergency_services.py     # Nearest service + routing (OSRM/Valhalla)
│   ├── voice_emotion.py          # Vocal emotion analysis (SpeechBrain)
│   └── test.py                   # Manual tests
├── data/
│   └── police.json               # Paris police stations dataset
├── dataset/                      # Fine-tuning dataset (2000 samples)
├── data_gen/                     # Dataset generation scripts
├── fine_tuning/                  # HuggingFace fine-tuning + W&B
├── test_depoly/                  # SageMaker deployment test
├── frontend/                     # Dispatcher dashboard (HTML/CSS/JS)
│   ├── index.html
│   ├── app.js
│   └── style.css
├── demo/
│   └── demo_mistral_hack.mp4     # Demo video
├── pyproject.toml
└── requirements.txt
```

---

## 🚀 Getting Started

1. **Create & activate a virtual environment**
   ```bash
   python -m venv venv
   source venv/bin/activate   # macOS/Linux
   venv\Scripts\activate      # Windows
   ```

2. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

3. **Configure environment variables**

   Create a `.env` file in `backend/`:
   ```env
   MISTRAL_API_KEY=...
   ELEVENLABS_API_KEY=...
   ELEVENLABS_VOICE_ID=...       # defaults to Sarah
   TWILIO_ACCOUNT_SID=...
   TWILIO_AUTH_TOKEN=...
   TWILIO_PHONE_NUMBER=...
   OPERATOR_PHONE=...            # SMS recipient after call ends
   PUBLIC_URL=...                # public hostname for Twilio webhook
   ```

4. **Run the service**
   ```bash
   cd backend
   uvicorn main:app --host 0.0.0.0 --port 8000
   ```
   The dashboard is served at `http://localhost:8000/static/index.html`.

5. **Expose to Twilio** (for real calls)

   Use [ngrok](https://ngrok.com) or any tunnel to expose port 8000, then set the Twilio webhook to:
   ```
   POST https://<your-public-url>/twilio/incoming
   ```

---

## 🛠️ Key Features

- **AI Dispatcher** — Mistral `ministral-8b` handles the conversation, asks the right questions, stays calm and professional
- **Real phone support** — Full Twilio Media Streams integration with barge-in (caller can interrupt the agent mid-sentence)
- **Voice Activity Detection** — RMS-based VAD, no external library needed
- **Streaming STT** — Mistral `voxtral-mini-2507` for fast, accurate transcription
- **Streaming TTS pipeline** — ElevenLabs generates audio sentence-by-sentence in parallel with the LLM stream
- **Automatic info extraction** — Structured JSON extracted after each exchange (type, severity, location, emotions, scores)
- **Geocoding + Street View** — Google Maps resolves the address and returns a street-level image for the dispatcher
- **Nearest service routing** — Haversine + OSRM/Valhalla to find and route the closest police, fire, or medical unit
- **Real-time dashboard** — WebSocket broadcast keeps all connected dashboards in sync instantly
- **Post-call SMS** — Twilio SMS sends a summary + safety instructions to the operator after each call
- **Vocal emotion analysis** — SpeechBrain wav2vec2-IEMOCAP classifies caller's emotional state in real time

---

## 📦 Dependencies

See `requirements.txt`. Core libraries: `fastapi`, `uvicorn`, `mistralai`, `twilio`, `elevenlabs`, `speechbrain`, `googlemaps`, `requests`, `python-dotenv`.

---

## 🧪 Testing

`backend/test.py` contains manual test snippets. For a full end-to-end test, use the browser interface at `/static/index.html` with the Voxtral WebSocket mode (no phone required).

---

## 🤝 Contributing

Contributions are welcome. Fork the repository, make your changes, and open a pull request. Please document any new endpoints or features.
