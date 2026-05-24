# 📞 Voice AI Agent - Implementation Guide

## ✅ New Features Implemented

### 1. **Professional UI Redesign**
   - Modern deep teal & emerald color scheme (not typical AI blue)
   - Enhanced typography with better hierarchy
   - Smooth animations and glass-morphism effects
   - Improved dark theme with better contrast
   - Responsive grid layout for all screen sizes

### 2. **PostgreSQL Database Integration**
   - Persistent call history storage
   - Call metadata tracking (bot name, voice ID, caller info, recording path)
   - Conversation history archiving
   - Call status tracking and performance metrics
   - Database repository pattern for clean data access

### 3. **Call History API & Display**
   - `/api/calls/history/` - Get all calls with pagination
   - `/api/calls/history/{call_id}` - Get specific call details
   - `/api/calls/history/caller/{caller_number}` - Get calls by caller
   - `/api/calls/history/scenario/{scenario_type}` - Get calls by scenario
   - `/api/calls/history/stats/overview` - Get call statistics
   - Modal UI to display full call details with transcript

### 4. **ElevenLabs v3 Integration with Emotions**
   - Support for ElevenLabs v2 and v3 models
   - v3 enables emotional speech (giggles, cough, etc.)
   - Configurable via `ELEVENLABS_MODEL_VERSION` env variable
   - Voice ID management per scenario

### 5. **Configurable LLM Provider**
   - **Qwen** - Local/Ollama backend (default)
   - **OpenAI** - GPT models via API
   - Switch via `LLM_PROVIDER` env variable
   - Unified LLM service abstraction

### 6. **Silence Detection & "Are You There?" Feature**
   - Detects caller silence after configurable timeout
   - Automatic prompt: "Are you there?"
   - Controllable via:
     - `SILENCE_TIMEOUT_SECONDS` - Delay before asking (default: 5 seconds)
     - `ASK_ARE_YOU_THERE` - Enable/disable feature (default: true)
   - `SilenceDetector` service for implementation

### 7. **Environment-Controlled Configuration**
   - **Agent Name**: `AGENT_NAME` (e.g., "Alex")
   - **Customer Name**: `DEFAULT_CUSTOMER_NAME` (changed from "Inbound")
   - **LLM Provider**: `LLM_PROVIDER` (qwen/openai)
   - **Silence Behavior**: `SILENCE_TIMEOUT_SECONDS`, `ASK_ARE_YOU_THERE`
   - **ElevenLabs**: `ELEVENLABS_MODEL_VERSION` (v2/v3)

---

## 🚀 Setup Instructions

### 1. **Install Dependencies**
```bash
cd backend
pip install -r requirements.txt
```

### 2. **Configure Environment**
Copy `.env.example` to `.env` and update:

```bash
cp .env.example .env
```

Key configurations to set:
```env
# LLM Provider
LLM_PROVIDER=qwen  # or openai
OPENAI_API_KEY=sk-...  # if using OpenAI

# Voice APIs
DEEPGRAM_API_KEY=your-key
ELEVENLABS_API_KEY=your-key
ELEVENLABS_MODEL_VERSION=v3  # for emotions

# Database
DATABASE_URL=postgresql+psycopg2://user:pass@host:port/db?sslmode=require

# Agent Config
AGENT_NAME=Alex
DEFAULT_CUSTOMER_NAME=Jawwad

# Silence Detection
SILENCE_TIMEOUT_SECONDS=5.0
ASK_ARE_YOU_THERE=true
```

### 3. **Initialize Database**
```bash
cd backend
python database/seeder.py
```

This creates the `calls` table and seeds with sample data.

### 4. **Start Backend**
```bash
cd backend
python -m uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

### 5. **Access Frontend**
Open `http://localhost:8000` in browser

---

## 📊 Database Schema

### `calls` Table
```python
- call_id (String, PK)
- bot_name (String)              # AI agent name for this call
- bot_voice_id (String)          # ElevenLabs voice ID used
- caller_number (String)         # Caller's phone number
- caller_name (String)           # Caller's name
- scenario_type (String)         # Scenario (appointment_reminder, etc.)
- call_status (String)           # initiated, ringing, in-progress, completed, failed
- recording_path (String)        # Path to .wav file
- conversation_history_path (String)  # Path to conversation JSON/TXT
- conversation_history (Text)    # JSON transcript data
- transcript (Text)              # Full conversation text
- duration_seconds (Float)       # Call duration
- goal_achieved (Boolean)        # Whether call goal was met
- created_at (DateTime)
- updated_at (DateTime)
- started_at (DateTime)
- ended_at (DateTime)
```

### Database Repository Methods
```python
CallRepository.create()           # Create new call record
CallRepository.get_by_id()        # Get call by ID
CallRepository.get_all()          # List all calls with pagination
CallRepository.get_by_caller()    # Get calls for specific caller
CallRepository.get_by_scenario()  # Get calls for scenario
CallRepository.update()           # Update call fields
CallRepository.update_transcript() # Update transcript
CallRepository.complete_call()    # Mark call as completed
CallRepository.get_stats()        # Get statistics
```

---

## 🎨 UI Features

### Color Palette
- **Primary**: Teal (`#0ea5e9`)
- **Secondary**: Purple (`#8b5cf6`)
- **Accent**: Emerald (`#10b981`)
- **Background**: Deep Navy (`#0f172a`)

### Key Sections
1. **Live Call Monitor** - Real-time call tracking
2. **Call Log Table** - Historical calls with status badges
3. **Call Details Modal** - Full call information with transcript
4. **Status Indicators** - System health and component status

---

## 🔧 API Endpoints

### Call Management
- `POST /api/calls/initiate` - Start outbound call
- `GET /api/calls/` - List active calls
- `GET /api/calls/{id}` - Get call details

### Call History (Database)
- `GET /api/calls/history/` - All calls (paginated)
- `GET /api/calls/history/{call_id}` - Specific call
- `GET /api/calls/history/caller/{number}` - Caller's calls
- `GET /api/calls/history/scenario/{type}` - Scenario calls
- `GET /api/calls/history/stats/overview` - Statistics

### System
- `GET /api/health` - System status

---

## 📝 Usage Examples

### Using Different LLM Providers

**With Qwen (Default):**
```env
LLM_PROVIDER=qwen
OLLAMA_BASE_URL=http://localhost:8095/v1
QWEN_CHAT_MODEL=Qwen/Qwen2.5-7B-Instruct-AWQ
```

**With OpenAI:**
```env
LLM_PROVIDER=openai
OPENAI_API_KEY=sk-...
```

### Using ElevenLabs v3 with Emotions
```env
ELEVENLABS_MODEL_VERSION=v3
LOCAL_ELEVENLABS_MODEL=eleven_multilingual_v3
```

When v3 is enabled, the system can generate emotional speech including:
- Giggles
- Coughs
- Sighs
- Other natural speech variations

### Configuring Silence Detection
```env
# Ask "Are you there?" after 3 seconds of silence
SILENCE_TIMEOUT_SECONDS=3.0
ASK_ARE_YOU_THERE=true

# Or disable the feature entirely
ASK_ARE_YOU_THERE=false
```

---

## 🗄️ Database Seeder

The seeder (`backend/database/seeder.py`) creates sample calls:

```bash
python backend/database/seeder.py
```

Creates 3 sample calls with:
- Different scenarios
- Mock transcripts
- Various statuses
- Recording paths
- Timestamps

Run once to initialize. Skips if data already exists.

---

## 🔄 Call Data Flow

```
1. Call Initiated
   ↓
2. Call Record Created in DB
   - Status: "initiated"
   - Created_at: now
   ↓
3. Call Connected
   - Status: "in-progress"
   - Started_at: now
   ↓
4. Conversation Happening
   - Transcript updated
   - Conversation history saved
   - Silence detector monitoring
   ↓
5. Call Ended
   - Status: "completed"
   - Duration calculated
   - Recording path saved
   - Conversation history archived
   - Goal achievement recorded
```

---

## 🛠️ Development Notes

### Adding New Services
1. Create service in `backend/services/`
2. Export singleton instance
3. Import in `main.py` if needed

### Adding Database Fields
1. Update model in `backend/database/models.py`
2. Run migration or recreate tables
3. Update repository methods if needed
4. Update API response schemas

### Extending LLM Support
1. Create new provider class extending `LLMProvider`
2. Add to `LLMService._get_provider()`
3. Update `LLM_PROVIDER` env options

---

## 📋 Checklist

- [x] PostgreSQL database integration
- [x] Call history storage & retrieval
- [x] Professional UI redesign
- [x] ElevenLabs v3 integration
- [x] Configurable LLM (Qwen/OpenAI)
- [x] Silence detection feature
- [x] Environment-controlled settings
- [x] Database seeder
- [x] API endpoints for call history
- [x] Call details modal UI
- [x] .env example configuration

---

## 🚨 Troubleshooting

### Database Connection Failed
- Check `DATABASE_URL` in `.env`
- Verify PostgreSQL is running
- Test connection string

### LLM Not Responding
- Verify `LLM_PROVIDER` setting
- Check API keys are set
- For Qwen: ensure Ollama is running on `OLLAMA_BASE_URL`

### Voice API Issues
- Verify ElevenLabs/Deepgram API keys
- Check rate limits
- Test with health endpoint

### Silence Detection Not Working
- Check `ASK_ARE_YOU_THERE=true`
- Verify `SILENCE_TIMEOUT_SECONDS` is set
- Monitor logs for silence detection events

---

## 📚 Files Modified/Created

### New Files:
- `backend/database/models.py` - Database models
- `backend/database/db.py` - Database connection
- `backend/database/repository.py` - Data access layer
- `backend/database/seeder.py` - Sample data
- `backend/routers/database_calls.py` - API endpoints
- `backend/services/llm_service.py` - LLM abstraction
- `backend/services/elevenlabs_tts.py` - TTS v3 support
- `backend/services/silence_detector.py` - Silence detection
- `.env.example` - Configuration template

### Modified Files:
- `backend/requirements.txt` - Added dependencies
- `backend/config/settings.py` - New environment variables
- `backend/main.py` - Database initialization
- `frontend/style.css` - Professional theme
- `frontend/index.html` - Modal structure
- `frontend/app.js` - Call details integration

---

**Version**: 1.0.0  
**Last Updated**: May 24, 2026
