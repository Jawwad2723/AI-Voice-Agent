# 📞 VoiceAI Agent — Outbound Call System

A production-minded voice AI agent that makes intelligent outbound calls using **Vapi.ai** for end-to-end STT → LLM → TTS, with a **FastAPI** backend and a clean single-page frontend.

---

## 🏗️ Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                        Browser (SPA)                            │
│   Phone # + Scenario + Params → POST /api/calls/initiate        │
└───────────────────────────┬─────────────────────────────────────┘
                            │ HTTP
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│                     FastAPI Backend                             │
│                                                                 │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────┐  │
│  │  /api/calls  │  │ /api/webhooks│  │  /api/scenarios      │  │
│  │   (router)   │  │  (router)    │  │  (router)            │  │
│  └──────┬───────┘  └──────┬───────┘  └──────────────────────┘  │
│         │                 │                                     │
│  ┌──────▼───────────────────────────────────────┐              │
│  │           Services Layer                     │              │
│  │  vapi_service.py  │  scenario_service.py      │              │
│  │  call_store.py    │  (prompt builder)         │              │
│  └──────┬───────────────────────────────────────┘              │
└─────────┼───────────────────────────────────────────────────────┘
          │ HTTPS REST
          ▼
┌─────────────────────────────────────────────────────────────────┐
│                        Vapi.ai                                  │
│                                                                 │
│   Telephony (Twilio) → STT (Deepgram Nova-2)                   │
│        ↓                                                        │
│   LLM (GPT-4o-mini) with scenario system prompt                │
│        ↓                                                        │
│   TTS (PlayHT) → Audio back to caller                          │
│        ↓                                                        │
│   Webhooks → POST /api/webhooks/vapi (events, transcript)      │
└─────────────────────────────────────────────────────────────────┘
```

### Component Responsibilities

| Layer | Component | Responsibility |
|---|---|---|
| **Routing** | `routers/calls.py` | Initiate, list, get, end calls |
| **Routing** | `routers/webhooks.py` | Receive real-time Vapi events |
| **Routing** | `routers/scenarios.py` | Expose scenario metadata |
| **Service** | `services/vapi_service.py` | Thin async wrapper for Vapi REST API |
| **Service** | `services/scenario_service.py` | Build Vapi assistant configs + prompts |
| **Service** | `services/call_store.py` | In-memory call records (swap for DB) |
| **Models** | `models/schemas.py` | Pydantic v2 request/response types |
| **Config** | `config/settings.py` | pydantic-settings env loading |
| **Frontend** | `frontend/index.html` | Single-page SPA |

---

## 🎭 Scenarios

Five production-ready outbound call campaigns are implemented:

### 1. 🏥 Appointment Reminder & Confirmation
**Agent:** Aria (warm, caring)  
**Flow:** Identify patient → confirm appointment details → handle confirm/reschedule/unsure  
**Required params:** `appointment_date`, `appointment_time`, `doctor_name`

### 2. 🎯 Lead Qualification
**Agent:** Alex (confident, professional)  
**Flow:** Warm opener → pain discovery → BANT-lite qualification → next-step booking  
**Required params:** `product_name`, `company_name`

### 3. 📊 Customer Satisfaction Survey
**Agent:** Sam (friendly, upbeat)  
**Flow:** Set expectations → overall satisfaction (1-10) → NPS → open feedback → close  
**Required params:** `product_or_service`, `purchase_date`

### 4. 💳 Payment Follow-up
**Agent:** Jordan (calm, professional)  
**Flow:** Identify reason for non-payment → offer resolution paths → confirm next steps  
**Required params:** `invoice_number`, `amount_due`, `due_date`

### 5. 🎟️ Event Confirmation
**Agent:** Riley (enthusiastic, welcoming)  
**Flow:** Confirm registration → logistics briefing → dietary/accessibility needs → build excitement  
**Required params:** `event_name`, `event_date`, `event_location`

---

## 🚀 Setup Instructions

### Prerequisites
- Python 3.11+
- A [Vapi.ai](https://vapi.ai) account (free tier works)
- A phone number provisioned in Vapi (buy in dashboard or bring your own Twilio)

### 1. Clone and install dependencies

```bash
cd backend
pip install -r requirements.txt
```

### 2. Configure environment

```bash
cp .env.example .env
```

Edit `.env`:

```env
VAPI_API_KEY=your_vapi_api_key_here
VAPI_PHONE_NUMBER_ID=your_vapi_phone_number_id_here
WEBHOOK_BASE_URL=https://your-ngrok-url.ngrok.io
```

**Where to find these values:**
- `VAPI_API_KEY` → Vapi Dashboard > Account > API Keys
- `VAPI_PHONE_NUMBER_ID` → Vapi Dashboard > Phone Numbers > click your number > copy the ID (UUID, not the phone number itself)

### 3. Set up webhooks (for local dev)

```bash
# Install ngrok
ngrok http 8000

# Copy the HTTPS URL (e.g. https://abc123.ngrok.io) to WEBHOOK_BASE_URL in .env
```

Vapi will POST events to `https://your-url.ngrok.io/api/webhooks/vapi`

### 4. Start the server

```bash
cd backend
uvicorn main:app --reload --port 8000
```

### 5. Open the UI

Navigate to `http://localhost:8000`

---

## 📡 API Reference

### `POST /api/calls/initiate`
Initiate an outbound call.

```json
{
  "phone_number": "+14155552671",
  "scenario_type": "appointment_reminder",
  "customer_name": "Jane Smith",
  "custom_params": {
    "appointment_date": "Monday, June 2nd",
    "appointment_time": "2:30 PM",
    "doctor_name": "Dr. Sarah Johnson",
    "clinic_name": "Wellness Clinic"
  }
}
```

**Response:**
```json
{
  "success": true,
  "call_id": "uuid-here",
  "vapi_call_id": "vapi-uuid",
  "message": "Call initiated to +14155552671",
  "status": "ringing"
}
```

### `GET /api/calls/`
List all calls (reverse chronological).

### `GET /api/calls/{call_id}`
Get call details. Syncs status from Vapi if call is still active.

### `DELETE /api/calls/{call_id}/end`
End an active call.

### `GET /api/scenarios/`
List all available scenarios with their metadata and example params.

### `POST /api/webhooks/vapi`
Vapi webhook receiver. Handles: `call-started`, `call-ended`, `end-of-call-report`, `hang`, `transcript`.

### `GET /api/health`
Health check. Returns `vapi_configured: true/false`.

---

## 🧩 Design Decisions

### Why Vapi instead of a custom pipeline?
Vapi provides a production-grade, latency-optimized pipeline where STT, LLM, and TTS are tightly integrated with low turn-latency (~800ms). Building this manually with Deepgram + OpenAI + ElevenLabs + Twilio would require WebSocket management, audio streaming, barge-in detection, and silence detection — significant engineering overhead for a first version. The architecture is designed so `vapi_service.py` can be swapped with a custom pipeline adapter without touching any other layer.

### Why in-memory call store?
`call_store.py` exposes a simple interface (`create`, `get`, `update`, `list_all`) that maps directly to a database. Replacing it with a PostgreSQL repository requires changing one file. For production: add SQLAlchemy + Alembic.

### Transient assistants vs. saved assistants
The assistant config is built inline per call rather than saving it to Vapi's assistant library. This makes each call fully dynamic (different doctor names, invoice amounts, etc.) without requiring N pre-created assistants. Trade-off: slightly more payload per call.

### System prompt architecture
Each scenario's system prompt follows a consistent structure:
1. **Agent persona** — name, role, company context
2. **Context block** — all dynamic parameters injected at runtime
3. **Conversation flow** — step-by-step with branching logic
4. **Core behavioral rules** — applies to all scenarios

This keeps prompts maintainable and testable independently of the API layer.

---

## 🔄 Extending the System

### Add a new scenario
1. Add to `ScenarioType` enum in `models/schemas.py`
2. Add `ScenarioInfo` entry to `SCENARIO_REGISTRY` in `scenario_service.py`
3. Add cases in `_build_system_prompt()` and `_build_first_message()`
4. Add the scenario card in `frontend/index.html` `SCENARIOS` array

### Swap to a custom STT/LLM/TTS pipeline
Replace `vapi_service.py` with a class implementing `create_outbound_call(...)` using:
- Twilio for telephony
- Deepgram streaming WebSocket for STT
- OpenAI / Claude for LLM
- ElevenLabs streaming TTS

The router layer doesn't need to change.

### Add a database
Replace `services/call_store.py` with a SQLAlchemy-based repository implementing the same interface.

---

## 📁 Project Structure

```
voice-ai-agent/
├── backend/
│   ├── main.py                    # FastAPI app + middleware
│   ├── requirements.txt
│   ├── .env.example
│   ├── config/
│   │   └── settings.py            # pydantic-settings
│   ├── models/
│   │   └── schemas.py             # Pydantic v2 models
│   ├── routers/
│   │   ├── calls.py               # Call management endpoints
│   │   ├── webhooks.py            # Vapi event receiver
│   │   └── scenarios.py           # Scenario metadata endpoints
│   └── services/
│       ├── vapi_service.py        # Vapi REST API client
│       ├── scenario_service.py    # Prompt builder + scenario registry
│       └── call_store.py          # In-memory call persistence
└── frontend/
    └── index.html                 # Single-page UI
```
