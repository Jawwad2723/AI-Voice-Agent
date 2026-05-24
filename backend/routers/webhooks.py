"""
Webhooks router — receives real-time events from Vapi.
Vapi sends POST requests here when call status changes, transcripts arrive, etc.
"""

import logging
from datetime import datetime
from fastapi import APIRouter, Request, Response
from models.schemas import CallStatus
from services.call_store import call_store

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/vapi")
async def vapi_webhook(request: Request):
    """
    Main Vapi webhook handler.

    Vapi sends events for:
    - call-started
    - call-ended
    - transcript (partial/final)
    - hang (user hung up)
    - function-call (tool use)
    - end-of-call-report (final summary with transcript)
    """
    try:
        payload = await request.json()
    except Exception:
        return Response(status_code=400, content="Invalid JSON")

    message = payload.get("message", {})
    event_type = message.get("type", "")
    call_data = message.get("call", {})
    vapi_call_id = call_data.get("id") or message.get("callId", "")

    logger.info(f"Vapi webhook | type={event_type} | call={vapi_call_id}")

    if not vapi_call_id:
        return {"received": True}

    record = call_store.get_by_vapi_id(vapi_call_id)
    if not record:
        # May arrive before we've stored the vapi_call_id — that's okay
        logger.debug(f"No internal record for vapi_call_id={vapi_call_id}")
        return {"received": True}

    handlers = {
        "call-started": _handle_call_started,
        "call-ended": _handle_call_ended,
        "end-of-call-report": _handle_end_of_call_report,
        "hang": _handle_hang,
        "transcript": _handle_transcript,
    }

    handler = handlers.get(event_type)
    if handler:
        handler(record.call_id, message)

    return {"received": True}


def _handle_call_started(call_id: str, message: dict):
    call_store.update(call_id, status=CallStatus.IN_PROGRESS)
    logger.info(f"Call started | {call_id}")


def _handle_call_ended(call_id: str, message: dict):
    ended_at = None
    duration = message.get("durationSeconds") or message.get("call", {}).get("durationSeconds")

    try:
        ended_at = datetime.utcnow()
    except Exception:
        pass

    updates = {
        "status": CallStatus.COMPLETED,
        "ended_at": ended_at,
    }
    if duration:
        updates["duration_seconds"] = int(duration)

    call_store.update(call_id, **updates)
    logger.info(f"Call ended | {call_id} | duration={duration}s")


def _handle_end_of_call_report(call_id: str, message: dict):
    """Final report with full transcript, summary, and recording."""
    updates = {
        "status": CallStatus.COMPLETED,
        "ended_at": datetime.utcnow(),
    }

    if message.get("summary"):
        updates["summary"] = message["summary"]

    if message.get("transcript"):
        updates["transcript"] = message["transcript"]

    if message.get("recordingUrl"):
        updates["recording_url"] = message["recordingUrl"]

    if message.get("durationSeconds"):
        updates["duration_seconds"] = int(message["durationSeconds"])

    # Derive outcome from summary keywords (simple heuristic)
    summary = updates.get("summary", "").lower()
    if summary:
        if any(word in summary for word in ["confirmed", "agreed", "yes", "scheduled"]):
            updates["outcome"] = "positive"
        elif any(word in summary for word in ["declined", "no", "not interested", "busy"]):
            updates["outcome"] = "declined"
        else:
            updates["outcome"] = "neutral"

    call_store.update(call_id, **updates)
    logger.info(f"End-of-call report received | {call_id}")


def _handle_hang(call_id: str, message: dict):
    call_store.update(call_id, status=CallStatus.COMPLETED, ended_at=datetime.utcnow())
    logger.info(f"Call hung up | {call_id}")


def _handle_transcript(call_id: str, message: dict):
    """Append transcript chunks — only store final transcripts."""
    if message.get("transcriptType") == "final":
        existing = call_store.get(call_id)
        if existing:
            role = message.get("role", "unknown")
            text = message.get("transcript", "")
            current = existing.transcript or ""
            updated = f"{current}\n[{role.upper()}]: {text}".strip()
            call_store.update(call_id, transcript=updated)
