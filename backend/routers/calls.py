"""
Calls router — endpoints for initiating, listing, and managing outbound calls.
Now powered by a custom Asterisk ARI pipeline instead of Vapi.ai.
"""

import logging
from fastapi import APIRouter, HTTPException, BackgroundTasks

from models.schemas import (
    InitiateCallRequest,
    InitiateCallResponse,
    CallListResponse,
    CallRecord,
    CallStatus,
)
from services.asterisk_service import asterisk_service
from services.call_store import call_store
from config.settings import settings

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/initiate", response_model=InitiateCallResponse)
async def initiate_call(
    request: InitiateCallRequest,
    background_tasks: BackgroundTasks,
):
    """
    Initiate an outbound AI call via the Asterisk ARI custom pipeline.

    Creates a call record immediately and originates the call through Asterisk.
    Returns the internal call_id plus the Asterisk channel ID for tracking.
    """
    if not settings.ASTERISK_HOST:
        raise HTTPException(
            status_code=503,
            detail="ASTERISK_HOST not configured. Please set it in your .env file.",
        )
    if not settings.DEEPGRAM_API_KEY:
        raise HTTPException(
            status_code=503,
            detail="DEEPGRAM_API_KEY not configured. Please set it in your .env file.",
        )
    if not settings.ELEVENLABS_API_KEY:
        raise HTTPException(
            status_code=503,
            detail="ELEVENLABS_API_KEY not configured. Please set it in your .env file.",
        )

    # Create an internal record first
    call_record = call_store.create(
        phone_number=request.phone_number,
        scenario_type=request.scenario_type,
        customer_name=request.customer_name,
        custom_params=request.custom_params or {},
    )

    try:
        ari_response = await asterisk_service.create_outbound_call(
            phone_number=request.phone_number,
            scenario_type=request.scenario_type,
            customer_name=request.customer_name,
            custom_params=request.custom_params or {},
            call_id=call_record.call_id,
        )

        ari_channel_id = ari_response.get("id")
        call_store.update(
            call_record.call_id,
            vapi_call_id=ari_channel_id,   # reusing field to store ARI channel ID
            status=CallStatus.RINGING,
        )

        logger.info(
            f"Call initiated | internal={call_record.call_id} | channel={ari_channel_id}"
        )

        return InitiateCallResponse(
            success=True,
            call_id=call_record.call_id,
            vapi_call_id=ari_channel_id,   # field name kept for schema compatibility
            message=f"Call initiated to {request.phone_number} via Asterisk",
            status=CallStatus.RINGING,
        )

    except Exception as e:
        logger.error(f"Failed to initiate call: {e}")
        call_store.update(call_record.call_id, status=CallStatus.FAILED)
        raise HTTPException(
            status_code=502,
            detail=f"Failed to initiate call via Asterisk ARI: {str(e)}",
        )


@router.get("/", response_model=CallListResponse)
async def list_calls():
    """List all calls with their current status."""
    calls = call_store.list_all()
    return CallListResponse(calls=calls, total=len(calls))


@router.get("/{call_id}", response_model=CallRecord)
async def get_call(call_id: str):
    """Get details for a specific call."""
    record = call_store.get(call_id)
    if not record:
        raise HTTPException(status_code=404, detail="Call not found")
    return record


@router.delete("/{call_id}/end")
async def end_call(call_id: str):
    """End an active call by tearing down its Asterisk bridge."""
    record = call_store.get(call_id)
    if not record:
        raise HTTPException(status_code=404, detail="Call not found")

    channel_id = record.vapi_call_id   # stored as the ARI channel ID
    if not channel_id:
        raise HTTPException(status_code=400, detail="No Asterisk channel ID associated with this call.")

    try:
        await asterisk_service._cleanup_call(call_id)
        # Also try to hang up the originating channel directly
        await asterisk_service._send_command("DELETE", f"channels/{channel_id}")
        call_store.update(call_id, status=CallStatus.COMPLETED)
        return {"success": True, "message": "Call ended"}
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Failed to end call: {str(e)}")
