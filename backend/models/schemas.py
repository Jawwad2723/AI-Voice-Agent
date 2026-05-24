"""
Pydantic models for the Voice AI Agent
"""

from pydantic import BaseModel, field_validator
from typing import Optional, Literal, Dict, Any, List
from datetime import datetime
from enum import Enum


class ScenarioType(str, Enum):
    APPOINTMENT_REMINDER = "appointment_reminder"
    LEAD_QUALIFICATION = "lead_qualification"
    CUSTOMER_SURVEY = "customer_survey"
    PAYMENT_FOLLOWUP = "payment_followup"
    EVENT_CONFIRMATION = "event_confirmation"


class CallStatus(str, Enum):
    INITIATED = "initiated"
    RINGING = "ringing"
    IN_PROGRESS = "in-progress"
    COMPLETED = "completed"
    FAILED = "failed"
    NO_ANSWER = "no-answer"
    BUSY = "busy"


# --- Request Models ---

class InitiateCallRequest(BaseModel):
    phone_number: str
    scenario_type: ScenarioType
    customer_name: str
    custom_params: Optional[Dict[str, Any]] = {}

    @field_validator("phone_number")
    @classmethod
    def validate_phone(cls, v):
        cleaned = v.replace(" ", "").replace("-", "").replace("(", "").replace(")", "")
        
        # Check if it's a short extension (digits only and length < 8) or local SIP endpoint
        is_short_extension = cleaned.isdigit() and len(cleaned) < 8
        is_sip_endpoint = "/" in cleaned or (not cleaned.isdigit() and len(cleaned) < 15 and not cleaned.startswith("+"))
        
        if is_short_extension or is_sip_endpoint:
            return cleaned
            
        if not cleaned.startswith("+"):
            cleaned = "+" + cleaned
        if len(cleaned) < 10:
            raise ValueError("Phone number too short")
        return cleaned

    model_config = {
        "json_schema_extra": {
            "example": {
                "phone_number": "+14155552671",
                "scenario_type": "appointment_reminder",
                "customer_name": "John Smith",
                "custom_params": {
                    "appointment_date": "Monday, June 2nd",
                    "appointment_time": "2:30 PM",
                    "doctor_name": "Dr. Sarah Johnson",
                    "clinic_name": "Wellness Clinic"
                }
            }
        }
    }


class ScenarioConfig(BaseModel):
    scenario_type: ScenarioType
    custom_params: Dict[str, Any] = {}


# --- Response Models ---

class CallRecord(BaseModel):
    call_id: str
    vapi_call_id: Optional[str] = None
    phone_number: str
    scenario_type: ScenarioType
    customer_name: str
    status: CallStatus
    started_at: datetime
    ended_at: Optional[datetime] = None
    duration_seconds: Optional[int] = None
    summary: Optional[str] = None
    transcript: Optional[str] = None
    recording_url: Optional[str] = None
    custom_params: Dict[str, Any] = {}
    outcome: Optional[str] = None


class InitiateCallResponse(BaseModel):
    success: bool
    call_id: str
    vapi_call_id: Optional[str] = None
    message: str
    status: CallStatus


class CallListResponse(BaseModel):
    calls: List[CallRecord]
    total: int


class ScenarioInfo(BaseModel):
    type: ScenarioType
    name: str
    description: str
    agent_name: str
    required_params: List[str]
    optional_params: List[str]
    example_params: Dict[str, Any]


# --- Webhook Models ---

class VapiWebhookPayload(BaseModel):
    message: Dict[str, Any]
