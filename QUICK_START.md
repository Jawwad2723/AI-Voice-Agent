# 🚀 Quick Reference - Voice AI Agent Updates

## Environment Variables Quick Setup

Copy this to your `.env` file:

```env
# ── Basic Setup ──
AGENT_NAME=Alex
DEFAULT_CUSTOMER_NAME=Jawwad
LLM_PROVIDER=qwen

# ── API Keys ──
DEEPGRAM_API_KEY=your-key
ELEVENLABS_API_KEY=your-key
OPENAI_API_KEY=sk-...  # if using OpenAI

# ── Database (IMPORTANT!) ──
DATABASE_URL=postgresql+psycopg2://avnadmin:password@pg-29fc1a3-jawwadhassan34-e909.h.aivencloud.com:10167/defaultdb?sslmode=require

# ── Speech Features ──
ELEVENLABS_MODEL_VERSION=v3  # v3 for emotions (giggles, cough)

# ── Smart Silence ──
SILENCE_TIMEOUT_SECONDS=5.0
ASK_ARE_YOU_THERE=true
```

---

## 5-Minute Setup

```bash
# 1. Install dependencies
cd backend
pip install -r requirements.txt

# 2. Initialize database
python database/seeder.py

# 3. Start server
python -m uvicorn main:app --reload

# 4. Open browser
# → http://localhost:8000
```

---

## New Features

| Feature | How to Use | Configuration |
|---------|-----------|-----------------|
| **Different Agent Names** | Change bot name dynamically | `AGENT_NAME=Alex` |
| **Customer Name** | Replace "Inbound Caller" | `DEFAULT_CUSTOMER_NAME=Jawwad` |
| **Emotions in Voice** | Use ElevenLabs v3 | `ELEVENLABS_MODEL_VERSION=v3` |
| **Switch LLM** | Use Qwen or OpenAI | `LLM_PROVIDER=qwen` or `openai` |
| **Silence Handling** | Ask "Are you there?" | `SILENCE_TIMEOUT_SECONDS=5.0` |
| **Call History** | Store & retrieve calls | Database auto-enabled |
| **Professional UI** | Beautiful dark theme | No setup needed |
| **Call Details** | Click call to see all info | Click row in table |

---

## API Endpoints

```bash
# Get all calls
curl http://localhost:8000/api/calls/history/

# Get specific call
curl http://localhost:8000/api/calls/history/{call_id}

# Get calls by caller
curl http://localhost:8000/api/calls/history/caller/+1-555-0101

# Get statistics
curl http://localhost:8000/api/calls/history/stats/overview

# Health check
curl http://localhost:8000/api/health
```

---

## Database Seeder

```bash
# Create sample data
python backend/database/seeder.py

# Creates 3 sample calls:
# - Appointment Reminder (Aria)
# - Lead Qualification (Ethan)
# - Customer Survey (Chloe)
```

---

## LLM Provider Switch

**Using Qwen (Local):**
```env
LLM_PROVIDER=qwen
OLLAMA_BASE_URL=http://localhost:8095/v1
```

**Using OpenAI:**
```env
LLM_PROVIDER=openai
OPENAI_API_KEY=sk-...
```

---

## ElevenLabs v3 (Emotions)

Enable emotional speech:
```env
ELEVENLABS_MODEL_VERSION=v3
LOCAL_ELEVENLABS_MODEL=eleven_multilingual_v3
```

Supports: giggles, coughs, sighs, natural variations

---

## Silence Detection Control

Customize when bot asks "Are you there?":

```env
# Ask after 5 seconds of silence (default)
SILENCE_TIMEOUT_SECONDS=5.0
ASK_ARE_YOU_THERE=true

# Ask after 10 seconds
SILENCE_TIMEOUT_SECONDS=10.0

# Disable feature
ASK_ARE_YOU_THERE=false
```

---

## UI Colors

- **Primary**: Teal (#0ea5e9)
- **Accent**: Emerald (#10b981)  
- **Secondary**: Purple (#8b5cf6)
- **Background**: Deep Navy (#0f172a)

---

## Database Fields Stored

Per call, the system now saves:
- ✅ Bot name & voice ID
- ✅ Caller number & name
- ✅ Full transcript
- ✅ Conversation history
- ✅ Recording file path
- ✅ Call duration
- ✅ Goal achieved (yes/no)
- ✅ All timestamps
- ✅ Call status

---

## Troubleshooting

**Can't connect to database?**
- Check `DATABASE_URL` in `.env`
- Verify PostgreSQL is running
- Test connection: `psql <your-connection-string>`

**LLM not responding?**
- If Qwen: ensure Ollama is running on `OLLAMA_BASE_URL`
- If OpenAI: verify `OPENAI_API_KEY` is set
- Check health endpoint: `/api/health`

**Silence detection not working?**
- Verify `ASK_ARE_YOU_THERE=true`
- Check logs for silence events
- Test with 5+ seconds of silence

---

## Files Changed

**New:**
- `backend/database/` - Database layer
- `backend/services/llm_service.py` - LLM abstraction
- `backend/services/elevenlabs_tts.py` - Voice v3
- `backend/services/silence_detector.py` - Silence handling
- `backend/routers/database_calls.py` - History API
- `IMPLEMENTATION_GUIDE.md` - Full guide
- `CHANGES_SUMMARY.md` - What was done
- `.env.example` - Configuration template

**Updated:**
- `backend/requirements.txt` - New dependencies
- `backend/config/settings.py` - New env variables
- `backend/main.py` - Database init
- `frontend/style.css` - Professional theme
- `frontend/app.js` - Call details modal

---

## One-Liner Commands

```bash
# Full setup from scratch
cd backend && pip install -r requirements.txt && python database/seeder.py && python -m uvicorn main:app --reload

# Only rebuild database
python backend/database/seeder.py

# Check system health
curl -s http://localhost:8000/api/health | python -m json.tool

# Get call stats
curl -s http://localhost:8000/api/calls/history/stats/overview | python -m json.tool
```

---

**Quick Links:**
- 📖 [Full Guide](IMPLEMENTATION_GUIDE.md)
- 📋 [Changes Summary](CHANGES_SUMMARY.md)
- ⚙️ [Configuration](v.example)

**Status**: ✅ Complete  
**Version**: 1.0.0
