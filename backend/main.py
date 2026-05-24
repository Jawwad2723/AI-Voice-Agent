"""
Voice AI Agent - FastAPI Backend
Outbound call system using Vapi.ai for STT/LLM/TTS
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import os
import logging

# Configure application logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)

from contextlib import asynccontextmanager
from routers import calls, webhooks, scenarios
from routers import database_calls
from config.settings import settings
from services.asterisk_service import asterisk_service
from database.db import init_db

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize database on startup (non-blocking if it fails)
    try:
        init_db()
        logging.info("✅ Database initialized successfully")
    except Exception as e:
        logging.warning(f"⚠️ Database initialization warning: {e}")
        logging.warning("App will run without database persistence. Call history will not be saved.")
    
    # Start Asterisk connection and RTP server
    await asterisk_service.start()
    yield
    # Stop Asterisk connection and RTP server
    await asterisk_service.stop()

app = FastAPI(
    title="Voice AI Agent",
    description="Outbound voice AI calling system powered by Asterisk ARI",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount routers
app.include_router(calls.router, prefix="/api/calls", tags=["Calls"])
app.include_router(webhooks.router, prefix="/api/webhooks", tags=["Webhooks"])
app.include_router(scenarios.router, prefix="/api/scenarios", tags=["Scenarios"])
app.include_router(database_calls.router, prefix="/api/calls/history", tags=["Call History"])

# Serve frontend static files
frontend_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "frontend"))
if os.path.exists(frontend_path):
    app.mount("/static", StaticFiles(directory=frontend_path), name="static")

    @app.get("/", response_class=FileResponse)
    async def serve_frontend():
        return FileResponse(os.path.join(frontend_path, "index.html"))


@app.get("/api/health")
async def health_check():
    return {
        "status": "healthy",
        "service": "Voice AI Agent",
        "pipeline": "custom",
        "asterisk_host": settings.ASTERISK_HOST,
        "deepgram_configured": bool(settings.DEEPGRAM_API_KEY),
        "elevenlabs_configured": bool(settings.ELEVENLABS_API_KEY),
        "llm_model": settings.QWEN_CHAT_MODEL,
        "llm_provider": settings.LLM_PROVIDER,
        "agent_name": settings.AGENT_NAME,
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
