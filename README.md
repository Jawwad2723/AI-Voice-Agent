# 🤖 AI Voice Agent — Production-Grade Telephony AI System

[![Python](https://img.shields.io/badge/Python-3.11+-blue?logo=python)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.110+-green?logo=fastapi)](https://fastapi.tiangolo.com)
[![Asterisk](https://img.shields.io/badge/Asterisk-20-orange?logo=asterisk)](https://www.asterisk.org)
[![License](https://img.shields.io/badge/License-MIT-purple)](LICENSE)

> A fully custom, production-minded AI voice agent that handles real phone calls end-to-end — from SIP telephony through speech recognition, language understanding, and expressive text-to-speech — with sub-second response latency.

📧 **Author:** Jawwad Hassan — [jawwadhassan76@gmail.com](mailto:jawwadhassan76@gmail.com)  
🔗 **Repository:** [github.com/Jawwad2723/AI-Voice-Agent](https://github.com/Jawwad2723/AI-Voice-Agent)  
🎥 **Demo Video:** [Watch Here](https://drive.google.com/file/d/1hHw0OmXI_ZQzWLA5b-3XohiXyUKS7BE3/view?usp=sharing)
---

## 📋 Table of Contents

- [Overview](#overview)
- [System Architecture](#system-architecture)
- [Component Deep-Dive](#component-deep-dive)
- [Real-Time Audio Pipeline](#real-time-audio-pipeline)
- [AI Pipeline](#ai-pipeline)
- [Scenario Engine](#scenario-engine)
- [Tech Stack](#tech-stack)
- [Project Structure](#project-structure)
- [Quick Start](#quick-start)
- [Configuration Reference](#configuration-reference)
- [API Reference](#api-reference)
- [Design Decisions](#design-decisions)

---

## Overview

This system is a fully custom-built AI voice agent that can autonomously conduct phone calls for multiple business scenarios — appointment reminders, lead qualification, customer surveys, payment follow-ups, and event confirmations.

**Unlike VAPI or similar wrapper services**, this agent is built ground-up:
- Direct SIP telephony integration via **Asterisk ARI** (no middleware abstraction)
- A custom **RTP audio engine** for real-time bidirectional audio
- A hand-crafted **streaming TTS pipeline** that starts speaking within 150ms of the LLM response
- A **producer-consumer jitter buffer** to eliminate voice breaks during streaming
- **ElevenLabs v3** with emotional audio tags for human-like speech (`[chuckles]`, `[sighs]`, etc.)
- **Deepgram Nova-2** for low-latency speech-to-text with voice activity detection
- **Qwen 2.5-7B-Instruct** (self-hosted) as the conversational LLM

---

## System Architecture

```
                        ┌─────────────────────────────────────────────────────┐
                        │                   CALLER (SIP Phone)                │
                        └────────────────────────┬────────────────────────────┘
                                                 │  SIP / RTP
                        ┌────────────────────────▼────────────────────────────┐
                        │              ASTERISK PBX (FreePBX / Asterisk 20)   │
                        │   ┌──────────────┐      ┌────────────────────────┐  │
                        │   │  Dialplan    │      │  ARI WebSocket Events  │  │
                        │   │ extensions   │      │  (StasisStart, etc.)   │  │
                        │   └──────┬───────┘      └──────────┬─────────────┘  │
                        │          │ ExternalMedia             │               │
                        │   ┌──────▼───────────────┐          │               │
                        │   │  UnicastRTP Bridge   │          │               │
                        └───┴──────┬───────────────┴──────────┼───────────────┘
                                   │                          │
                     RTP (ulaw)    │              ARI REST +  │  WebSocket
                    ┌──────────────▼──────────────────────────▼──────────────┐
                    │                  FASTAPI BACKEND (Python 3.11)          │
                    │                                                          │
                    │  ┌─────────────────┐    ┌──────────────────────────┐   │
                    │  │   RTP Server    │    │    Asterisk Service       │   │
                    │  │  (UDP Socket)   │    │  (ARI REST + WS Client)  │   │
                    │  │  Port 18080-    │    │                          │   │
                    │  │    18180        │    │  • Call lifecycle mgmt   │   │
                    │  └────────┬────────┘    │  • Bridge orchestration  │   │
                    │           │             │  • ExternalMedia setup   │   │
                    │           │             └──────────────────────────┘   │
                    │           │                                              │
                    │  ┌────────▼────────────────────────────────────────┐   │
                    │  │              CUSTOM AI PIPELINE                   │   │
                    │  │                                                   │   │
                    │  │  ┌─────────────┐  ┌──────────────┐  ┌────────┐  │   │
                    │  │  │  Deepgram   │  │  Qwen 2.5-7B │  │Eleven  │  │   │
                    │  │  │  Nova-2 STT │→ │  (Ollama API)│→ │Labs v3 │  │   │
                    │  │  │  WebSocket  │  │  LLM Chat    │  │  TTS   │  │   │
                    │  │  └─────────────┘  └──────────────┘  └────────┘  │   │
                    │  │                                                   │   │
                    │  │  • VAD (Voice Activity Detection)                │   │
                    │  │  • Barge-in interruption                         │   │
                    │  │  • Streaming TTS → RTP jitter buffer             │   │
                    │  │  • Silence detection → "Are you there?"          │   │
                    │  └───────────────────────────────────────────────────┘  │
                    │                                                          │
                    │  ┌──────────────────┐    ┌────────────────────────┐    │
                    │  │  PostgreSQL DB   │    │   REST API + Web UI    │    │
                    │  │  (Aiven Cloud)   │    │   (Call management)    │    │
                    │  └──────────────────┘    └────────────────────────┘    │
                    └──────────────────────────────────────────────────────────┘
```

---

## Component Deep-Dive

### 1. Asterisk ARI Integration (`services/asterisk_service.py`)

The system connects to Asterisk via the **Asterisk REST Interface (ARI)** — both its REST API and its WebSocket event stream.

**Inbound call flow:**
1. Asterisk dialplan routes incoming calls to the `asterisk-ai-voice-agent` Stasis application
2. `AsteriskService` receives the `StasisStart` WebSocket event
3. The call is answered via `POST /ari/channels/{id}/answer`
4. An **ExternalMedia channel** is created, tunneling the audio stream to our Python RTP server via UDP
5. A **mixing bridge** joins the caller channel and ExternalMedia channel so audio flows both ways
6. The AI pipeline is started and attached to the call

**Outbound call flow:**
1. REST API receives outbound call request with scenario + customer details
2. `POST /ari/channels` originates the call to the PJSIP endpoint
3. Same pipeline starts when the callee answers (`StasisStart` event with `call_id` arg)

**Key design decision:** Using ARI directly (not AGI or AMI) gives us full programmatic control over channels, bridges, and media without blocking Asterisk's main thread.

---

### 2. Custom RTP Server (`services/rtp_server.py`)

A raw UDP socket server that handles bidirectional G.711 μ-law (ulaw) audio at 8kHz.

**Receiving audio (caller → AI):**
- Uses `loop.add_reader()` for non-blocking async reads on the UDP socket
- Parses RTP headers (version, SSRC, payload type, sequence, timestamp)
- Filters echo by ignoring our own outbound SSRC
- Delivers raw ulaw payloads to the pipeline via callback

**Sending audio (AI → caller):**

The `stream_audio()` method implements a **producer-consumer jitter buffer**:

```
ElevenLabs HTTP Stream
        │
        ▼
┌─────────────────┐     ┌──────────────────────────────┐
│  _download()    │────►│   asyncio.Queue (frame buf)   │
│  (async task)   │     │   160-byte frames (20ms each) │
└─────────────────┘     └──────────────────────────────┘
                                       │
                    Wait for 300ms     │
                    pre-buffer fill    │
                                       ▼
                        ┌──────────────────────────────┐
                        │  Sender loop                  │
                        │  wall-clock timing:           │
                        │  next_send = loop.time()      │
                        │  sleep = next_send - now      │
                        │  (compensates for drift)      │
                        └──────────────┬───────────────┘
                                       │ RTP packets (20ms)
                                       ▼
                                 Asterisk ► Caller
```

This eliminates voice breaks caused by HTTP chunk bursts/gaps from ElevenLabs.

---

### 3. AI Pipeline (`services/custom_pipeline.py`)

The core real-time conversation engine. Every active call gets its own `CustomPipeline` instance running independently.

**Turn-taking logic:**

```
Caller audio (ulaw)
      │
      ├──► Deepgram STT WebSocket (streaming)
      │         │
      │         ▼
      │    Transcript chunks
      │         │ speech_final=True?
      │         ▼
      │    LLM Request (Qwen 2.5-7B)
      │         │
      │         ▼
      │    Response text (with [emotion tags])
      │         │
      │         ▼
      │    ElevenLabs v3 Streaming TTS
      │         │
      │         ▼
      └──► RTP jitter buffer → Caller
```

**Voice Activity Detection (VAD):**
- RMS energy of each ulaw frame is measured via `audioop.rms()`
- Threshold: RMS ≥ 600 → user is speaking
- When user starts speaking mid-AI-response → **barge-in**: `current_playback_task.cancel()` stops TTS immediately
- 40 frames (~800ms) of silence after speech → end of turn

**Silence Detection:**
- If neither user nor AI speaks for 5 seconds → "Are you there?" prompt
- Second 5-second silence → call terminated cleanly

---

### 4. Speech-to-Text — Deepgram Nova-2

- Connected via **WebSocket** (persistent connection per call)
- Audio streamed in real-time as ulaw frames arrive from RTP
- Uses `speech_final=True` events (endpoint detection) to trigger LLM, not just `is_final`
- Model: `nova-2`, encoding: `mulaw`, sample rate: `8000Hz`

**Why Deepgram over Whisper?** Real-time WebSocket streaming with endpoint detection is essential for natural conversation — batch transcription would add 1-3s of latency per turn.

---

### 5. Language Model — Qwen 2.5-7B Instruct (AWQ)

- Self-hosted via Ollama on a dedicated GPU server (`http://38.247.189.107:8095/v1`)
- OpenAI-compatible API (`/v1/chat/completions`)
- AWQ quantization for fast inference on consumer GPUs
- Full conversation history maintained per call for context continuity

**System prompt engineering:**
- Scenario-aware prompts (5 distinct scenarios)
- Includes ElevenLabs v3 **audio tag instructions** so the LLM naturally embeds `[chuckles]`, `[sighs]`, `[warmly]`, etc. in responses
- Strict behavioral rules: no bullet points (it's voice), natural speech patterns, graceful interruption handling

---

### 6. Text-to-Speech — ElevenLabs v3

- Model: `eleven_v3` (latest, supports emotional audio tags)
- Format: `ulaw_8000` (direct G.711 output, no transcoding needed)
- Streams via `httpx` `client.stream()` — first audio plays within ~150ms
- Voice settings tuned for natural speech: `stability: 0.45`, `style: 0.35`, `use_speaker_boost: true`
- **Per-scenario voices**: each scenario uses a distinct ElevenLabs voice ID

**Emotional expression example:**
```
LLM output:  "Oh, no worries at all! [chuckles] These things happen."
ElevenLabs:  Renders an actual audible chuckle in the voice output
```

---

## Real-Time Audio Pipeline

```
Timing budget per conversational turn:

  Caller speaks      [~~~~~~~~~~~~~~~]
  STT (streaming)    [───────────────►] speech_final
  LLM inference                        [~~~~~►] ~800ms (Qwen 2.5-7B AWQ)
  TTS first audio                              [►] ~150ms (streaming)
  Caller hears AI                              [≈≈≈≈≈≈≈≈≈≈≈≈≈≈≈≈≈≈≈≈]
                                         ↑
                              Total latency: ~1.0–1.5s
```

**Audio codec path:** ulaw (G.711μ) throughout — Asterisk → RTP → Deepgram → ElevenLabs output format `ulaw_8000` → RTP → Asterisk. **No transcoding at any step.**

---

## Scenario Engine

Five pre-built campaign scenarios, each with:
- Unique agent persona and name
- Distinct ElevenLabs voice ID
- Scenario-specific system prompt with conversation flow (BANT-lite for sales, appointment confirmation flow, etc.)
- Parameterized first message (customer name, appointment details, etc.)
- Example parameters for testing

| Scenario | Agent | Use Case |
|---|---|---|
| Appointment Reminder | Aria | Patient appointment confirmation & rescheduling |
| Lead Qualification | Ethan | BANT-based sales qualification |
| Customer Survey | Chloe | Post-purchase NPS & feedback |
| Payment Follow-up | Marcus | Overdue invoice resolution |
| Event Confirmation | David | Event registration & logistics |

---

## Tech Stack

| Layer | Technology | Why |
|---|---|---|
| **Telephony** | Asterisk 20 + PJSIP | Industry-standard open-source PBX with ARI for programmatic control |
| **Call Control** | Asterisk ARI (REST + WebSocket) | Full control over channels, bridges, media without blocking Asterisk |
| **Audio Transport** | Custom UDP RTP Engine | Raw socket gives us full control over timing, SSRC filtering, jitter buffering |
| **STT** | Deepgram Nova-2 (WebSocket streaming) | Sub-100ms incremental transcripts with built-in endpoint detection |
| **LLM** | Qwen 2.5-7B-Instruct-AWQ (self-hosted) | Fast AWQ-quantized inference on own GPU, no API costs per call |
| **TTS** | ElevenLabs eleven_v3 (HTTP streaming) | Emotional audio tags, ulaw_8000 native output, streaming support |
| **Backend** | FastAPI + Python 3.11 asyncio | Fully async — one event loop handles all concurrent calls efficiently |
| **Database** | PostgreSQL (Aiven Cloud) + SQLAlchemy | Call history, transcripts, duration, status persistence |
| **Frontend** | Vanilla JS + CSS | Lightweight call management dashboard |

---

## Project Structure

```
voice-ai-agent/
├── backend/
│   ├── main.py                    # FastAPI app, lifespan, router registration
│   ├── config/
│   │   └── settings.py            # Pydantic settings (env-driven config)
│   ├── services/
│   │   ├── asterisk_service.py    # ARI WebSocket listener, call orchestration
│   │   ├── rtp_server.py          # UDP RTP engine, jitter buffer, streaming
│   │   ├── custom_pipeline.py     # Per-call AI pipeline (STT→LLM→TTS)
│   │   ├── scenario_service.py    # Scenario registry, prompt builder, first msg
│   │   ├── call_store.py          # In-memory call state cache
│   │   ├── elevenlabs_tts.py      # ElevenLabs TTS helper
│   │   ├── llm_service.py         # LLM abstraction (Qwen / OpenAI)
│   │   └── silence_detector.py    # Silence timeout logic
│   ├── models/
│   │   └── schemas.py             # Pydantic models (CallRecord, ScenarioType, etc.)
│   ├── database/
│   │   ├── db.py                  # SQLAlchemy engine + init_db()
│   │   ├── models.py              # ORM models (Call table)
│   │   └── repository.py          # CRUD operations
│   └── routers/
│       ├── calls.py               # POST /api/calls/ (initiate outbound)
│       ├── database_calls.py      # GET /api/calls/history
│       ├── scenarios.py           # GET /api/scenarios/
│       └── webhooks.py            # Webhook endpoints
├── asterisk_configurations/       # Pre-built Asterisk config files (copy to /etc/asterisk)
│   ├── ari.conf                   # ARI interface configuration
│   ├── pjsip.conf                 # PJSIP endpoints, transports, auth
│   └── extensions.conf            # Dialplan routing to Stasis app
├── frontend/
│   ├── index.html                 # Dashboard UI
│   ├── app.js                     # Call management, live status polling
│   └── style.css                  # UI styling
└── .env.example                   # All configuration variables documented
```

---

## Quick Start

### Prerequisites

- Python 3.11+
- Asterisk 20 with ARI enabled
- PostgreSQL database (or use Aiven Cloud free tier)
- Deepgram API key
- ElevenLabs API key
- Qwen 2.5-7B model (Ollama) or OpenAI API key

---

### 1. Install Asterisk

Install Asterisk 20 on your system (Ubuntu/Debian):

```bash
sudo apt update && sudo apt install -y asterisk
```

Or build from source for Asterisk 20 on Ubuntu:

```bash
cd /usr/src
sudo wget http://downloads.asterisk.org/pub/telephony/asterisk/asterisk-20-current.tar.gz
sudo tar xvzf asterisk-20-current.tar.gz
cd asterisk-20*/
sudo contrib/scripts/install_prereq install
sudo ./configure
sudo make
sudo make install
sudo make samples        # installs default config files to /etc/asterisk
sudo make config         # installs init scripts
sudo ldconfig
```

Verify the installation:

```bash
asterisk -V
# Expected output: Asterisk 20.x.x
```

---

### 2. Apply Configuration Files

This repository includes pre-built Asterisk configuration files in the `asterisk_configurations/` folder. Copy them directly into `/etc/asterisk`, replacing the defaults:

```bash
sudo cp asterisk_configurations/* /etc/asterisk/
```

> **What these files configure:**
> - `ari.conf` — Enables the ARI interface and creates the `ariuser` credentials used by the backend
> - `pjsip.conf` — Sets up PJSIP transport, registers extension **1002** as a SIP account, and defines endpoint **5001** as the AI agent's outbound target
> - `extensions.conf` — Dialplan that routes all calls through the `asterisk-ai-voice-agent` Stasis application

---

### 3. Register a SIP Account (Extension 1002)

Extension **1002** is pre-configured in `pjsip.conf` as your SIP client account. Register it in any softphone (Zoiper, Linphone, MicroSIP, etc.):

| Field | Value |
|---|---|
| **Username / Extension** | `1002` |
| **Password** | `1002` *(or as set in `pjsip.conf`)* |
| **Domain / Server** | `<your-asterisk-server-ip>` |
| **Port** | `5060` |
| **Transport** | `UDP` |

Once registered, your softphone will show as **Online/Connected**.

---

### 4. Reload Asterisk

Apply the new configuration without restarting the service:

```bash
sudo asterisk -rx "core reload"
```

Or if Asterisk is not running, start it:

```bash
sudo systemctl start asterisk
```

Verify that ARI is active:

```bash
sudo asterisk -rx "ari show status"
# Expected: ARI enabled, HTTP server running
```

---

### 5. Make a Test Call (Dial 5001)

With extension **1002** registered in your softphone, dial **5001** to reach the AI agent:

```
Dial: 5001
```

- **5001** is the AI agent's endpoint defined in `pjsip.conf`
- Asterisk's dialplan will route the call into the `asterisk-ai-voice-agent` Stasis application
- The FastAPI backend must be running (see Step 7) for the AI pipeline to answer

> **Outbound calls** (backend-initiated) also originate to `PJSIP/5001`. This is the endpoint string used in the `POST /api/calls/` request body.

---

### 6. Asterisk ARI Setup (Manual Reference)

If you prefer to configure ARI manually instead of using the provided config files, here are the relevant sections:

Enable ARI in `/etc/asterisk/ari.conf`:
```ini
[general]
enabled = yes
pretty = yes
allowed_origins = *

[ariuser]
type = user
read_only = no
password = aripassword
```

Configure your dialplan (`/etc/asterisk/extensions.conf`):
```ini
[from-internal]
exten => _X.,1,NoOp(Incoming call to AI agent)
 same => n,Stasis(asterisk-ai-voice-agent)
 same => n,Hangup()
```

Reload Asterisk: `asterisk -rx "core reload"`

---

### 7. Backend Setup

```bash
cd backend
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# Edit .env with your API keys and configuration
uvicorn main:app --host 0.0.0.0 --port 8000
```

### 8. Access the Dashboard

Open `http://localhost:8000` in your browser.

---

## Configuration Reference

| Variable | Description | Example |
|---|---|---|
| `ASTERISK_HOST` | Asterisk server IP | `127.0.0.1` |
| `ASTERISK_ARI_USERNAME` | ARI username | `ariuser` |
| `ASTERISK_ARI_PASSWORD` | ARI password | `aripassword` |
| `DEEPGRAM_API_KEY` | Deepgram API key | `2859954...` |
| `ELEVENLABS_API_KEY` | ElevenLabs API key | `sk_a7da...` |
| `LOCAL_ELEVENLABS_MODEL` | ElevenLabs model | `eleven_v3` |
| `OLLAMA_BASE_URL` | Qwen/Ollama base URL | `http://host:8095/v1` |
| `QWEN_CHAT_MODEL` | Model name | `Qwen/Qwen2.5-7B-Instruct-AWQ` |
| `DATABASE_URL` | PostgreSQL connection string | `postgresql+psycopg2://...` |
| `DEFAULT_INBOUND_SCENARIO` | Scenario for inbound calls | `appointment_reminder` |
| `DEFAULT_CUSTOMER_NAME` | Fallback caller name | `Jawwad` |
| `SILENCE_TIMEOUT_SECONDS` | Seconds before "Are you there?" | `5.0` |
| `RTP_PORT_RANGE_START` | First UDP port for RTP | `18080` |
| `RTP_PORT_RANGE_END` | Last UDP port for RTP | `18180` |

---

## API Reference

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/api/health` | System health + config status |
| `POST` | `/api/calls/` | Initiate outbound call |
| `GET` | `/api/calls/` | List active calls |
| `DELETE` | `/api/calls/{id}` | Hang up a call |
| `GET` | `/api/calls/history` | Call history from database |
| `GET` | `/api/scenarios/` | List available scenarios |

**Example — initiate outbound call:**
```bash
curl -X POST http://localhost:8000/api/calls/ \
  -H "Content-Type: application/json" \
  -d '{
    "phone_number": "PJSIP/5001",
    "scenario_type": "appointment_reminder",
    "customer_name": "John Smith",
    "custom_params": {
      "appointment_date": "Monday, June 2nd",
      "appointment_time": "2:30 PM",
      "doctor_name": "Dr. Sarah Johnson",
      "clinic_name": "Wellness Medical Center"
    }
  }'
```

---

## Design Decisions

### Why not use VAPI / Retell / Bland?

These platforms abstract away the telephony and pipeline details. For a production-minded system, direct control over the full stack means:
- **Lower latency**: No extra hop through a third-party relay
- **Full observability**: Every RTP packet, SSRC, and STT event is logged
- **No per-minute API costs** for the LLM (self-hosted Qwen)
- **Customizable pipeline**: The jitter buffer, VAD thresholds, barge-in behavior are all tunable

### Why Asterisk over Twilio/Vonage?

Asterisk runs on-premises, giving full control over SIP trunks and no per-minute fees for call handling. The ARI interface provides WebSocket-driven event streaming and a clean REST API for channel manipulation — comparable to Twilio's TwiML but without vendor lock-in.

### Why ulaw (G.711μ) throughout?

G.711μ is the native codec for PSTN telephony. By requesting `ulaw_8000` output directly from ElevenLabs and feeding ulaw directly into Deepgram, **zero transcoding occurs** in the pipeline. This eliminates audio quality degradation and saves ~5-10ms of processing per frame.

### Why a producer-consumer jitter buffer?

ElevenLabs HTTP streaming delivers audio in variable-sized bursts (the synthesizer produces words in chunks). Without buffering, this causes:
- **Burst frames**: Multiple 20ms RTP frames sent simultaneously → Asterisk jitter buffer overflow → crackle
- **Gap frames**: Silence while waiting for next HTTP chunk → audible breaks

The solution: a 300ms pre-buffer + wall-clock-timed sender that maintains a steady 20ms/packet cadence regardless of HTTP delivery timing.

---

## Contact

**Jawwad Hassan**  
AI Engineer  
📧 [jawwadhassan76@gmail.com](mailto:jawwadhassan76@gmail.com)  
🔗 [github.com/Jawwad2723/AI-Voice-Agent](https://github.com/Jawwad2723/AI-Voice-Agent)