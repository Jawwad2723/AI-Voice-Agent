"""
Vapi.ai API integration service.
Handles all communication with the Vapi REST API.
"""

import httpx
import logging
from typing import Dict, Any, Optional

from config.settings import settings
from models.schemas import ScenarioType
from services.scenario_service import build_vapi_assistant_config

logger = logging.getLogger(__name__)

VAPI_BASE_URL = "https://api.vapi.ai"


class VapiService:
    """Thin async wrapper around the Vapi REST API."""

    def __init__(self):
        self.api_key = settings.VAPI_API_KEY
        self.phone_number_id = settings.VAPI_PHONE_NUMBER_ID
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    async def create_outbound_call(
        self,
        phone_number: str,
        scenario_type: ScenarioType,
        customer_name: str,
        custom_params: Dict[str, Any],
        call_id: str,
    ) -> Dict[str, Any]:
        """
        Initiate an outbound call via Vapi.
        The assistant is defined inline (transient assistant) so we don't
        need to pre-create assistants in Vapi's dashboard.
        """
        assistant_config = build_vapi_assistant_config(
            scenario_type=scenario_type,
            customer_name=customer_name,
            custom_params=custom_params,
        )

        payload = {
            "phoneNumberId": self.phone_number_id,
            "customer": {
                "number": phone_number,
                "name": customer_name,
            },
            "assistant": assistant_config,
            "metadata": {
                "internal_call_id": call_id,
                "scenario_type": scenario_type.value,
                "customer_name": customer_name,
            },
        }

        # Add webhook server URL if configured
        if settings.WEBHOOK_BASE_URL and settings.WEBHOOK_BASE_URL != "https://your-ngrok-url.ngrok.io":
            payload["serverUrl"] = f"{settings.WEBHOOK_BASE_URL}/api/webhooks/vapi"

        logger.info(f"Creating Vapi call for {phone_number} | scenario={scenario_type.value}")

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{VAPI_BASE_URL}/call",
                headers=self.headers,
                json=payload,
            )
            response.raise_for_status()
            data = response.json()
            logger.info(f"Vapi call created: {data.get('id')}")
            return data

    async def get_call(self, vapi_call_id: str) -> Dict[str, Any]:
        """Fetch call details from Vapi."""
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.get(
                f"{VAPI_BASE_URL}/call/{vapi_call_id}",
                headers=self.headers,
            )
            response.raise_for_status()
            return response.json()

    async def end_call(self, vapi_call_id: str) -> Dict[str, Any]:
        """End an active call."""
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.delete(
                f"{VAPI_BASE_URL}/call/{vapi_call_id}",
                headers=self.headers,
            )
            response.raise_for_status()
            return response.json()

    async def list_calls(self, limit: int = 20) -> Dict[str, Any]:
        """List recent calls from Vapi."""
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.get(
                f"{VAPI_BASE_URL}/call",
                headers=self.headers,
                params={"limit": limit},
            )
            response.raise_for_status()
            return response.json()


# Module-level singleton
vapi_service = VapiService()
