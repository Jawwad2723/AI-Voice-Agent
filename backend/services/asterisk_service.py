import asyncio
import httpx
import websockets
import json
import logging
from datetime import datetime, timezone
from typing import Dict, Any, Optional

from config.settings import settings
from models.schemas import CallStatus
from services.call_store import call_store
from services.rtp_server import RTPServer

logger = logging.getLogger(__name__)

# Initialize the global RTP Server instance
rtp_server = RTPServer(
    host=settings.RTP_SERVER_HOST,
    port_range_start=settings.RTP_PORT_RANGE_START,
    port_range_end=settings.RTP_PORT_RANGE_END
)

class AsteriskService:
    def __init__(self):
        self.host = settings.ASTERISK_HOST
        self.port = settings.ASTERISK_PORT
        self.username = settings.ASTERISK_ARI_USERNAME
        self.password = settings.ASTERISK_ARI_PASSWORD
        self.app_name = settings.ASTERISK_ARI_APP
        
        self.auth = httpx.BasicAuth(self.username, self.password)
        self.base_url = f"http://{self.host}:{self.port}/ari"
        self.ws_url = f"ws://{self.host}:{self.port}/ari/events?api_key={self.username}:{self.password}&app={self.app_name}"

        # Maps call_id -> dict of call info (bridge_id, caller_channel_id, external_media_channel_id, pipeline)
        self.active_calls: Dict[str, Dict[str, Any]] = {}
        # Maps channel_id -> call_id
        self.channel_to_call_id: Dict[str, str] = {}
        
        self.listener_task: Optional[asyncio.Task] = None
        self.running = False
        
        # Will be imported dynamically to avoid circular dependency
        self.pipeline_class = None

    async def start(self):
        self.running = True
        await rtp_server.start()
        self.listener_task = asyncio.create_task(self._listen_events_loop())
        logger.info("Asterisk Service started")

    async def stop(self):
        self.running = False
        if self.listener_task:
            self.listener_task.cancel()
            try:
                await self.listener_task
            except asyncio.CancelledError:
                pass
        
        await rtp_server.stop()
        
        # Clean up any remaining active calls
        for call_id in list(self.active_calls.keys()):
            await self._cleanup_call(call_id)
            
        logger.info("Asterisk Service stopped")

    async def _send_command(self, method: str, path: str, params: Optional[Dict[str, Any]] = None, json_data: Optional[Dict[str, Any]] = None) -> Optional[Dict[str, Any]]:
        """Utility to send REST commands to Asterisk ARI."""
        url = f"{self.base_url}/{path}"
        try:
            async with httpx.AsyncClient() as client:
                if method == "POST":
                    response = await client.post(url, params=params, json=json_data, auth=self.auth, timeout=10.0)
                elif method == "DELETE":
                    response = await client.delete(url, params=params, auth=self.auth, timeout=10.0)
                elif method == "GET":
                    response = await client.get(url, params=params, auth=self.auth, timeout=10.0)
                else:
                    raise ValueError(f"Unsupported HTTP method: {method}")
                
                if response.status_code in (200, 201, 204):
                    return response.json() if response.content else {}
                else:
                    if method == "DELETE" and response.status_code == 404:
                        logger.debug(f"ARI resource already gone command={path}")
                    else:
                        logger.error(f"ARI error command={path} code={response.status_code} body={response.text}")
                    return None
        except Exception as e:
            logger.error(f"ARI connection error command={path}: {e}")
            return None

    async def create_outbound_call(
        self,
        phone_number: str,
        scenario_type: Any,
        customer_name: str,
        custom_params: Dict[str, Any],
        call_id: str,
    ) -> Dict[str, Any]:
        """Originate an outbound call via Asterisk ARI."""
        # If the phone number already specifies the channel technology (e.g. PJSIP/5001 or SIP/zoiper), use it as is
        if "/" in phone_number:
            dial_endpoint = phone_number
        else:
            dial_endpoint = settings.ASTERISK_OUTBOUND_ENDPOINT_FORMAT.format(phone_number=phone_number)
        
        logger.info(f"Originating outbound call to {dial_endpoint} with call_id={call_id}")
        
        params = {
            "endpoint": dial_endpoint,
            "app": self.app_name,
            "appArgs": f"call_id:{call_id}",
            "callerId": customer_name
        }
        
        # Call POST /channels to originate the call
        response = await self._send_command("POST", "channels", params=params)
        
        if not response or not response.get("id"):
            raise RuntimeError(f"Asterisk ARI failed to originate channel for {dial_endpoint}")
            
        channel_id = response["id"]
        logger.info(f"Outbound channel originated. Channel ID: {channel_id}")
        
        # Map channel to call
        self.channel_to_call_id[channel_id] = call_id
        
        return {
            "id": channel_id,
            "status": "ringing"
        }

    async def _listen_events_loop(self):
        """Websocket event listener loop with reconnection logic."""
        while self.running:
            try:
                async with websockets.connect(self.ws_url) as websocket:
                    logger.info("Connected to Asterisk ARI WebSocket")
                    while self.running:
                        message = await websocket.recv()
                        event = json.loads(message)
                        asyncio.create_task(self._handle_event(event))
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Asterisk ARI WebSocket error: {e}. Reconnecting in 5 seconds...")
                await asyncio.sleep(5)

    async def _handle_event(self, event: Dict[str, Any]):
        """Parse and handle ARI events."""
        event_type = event.get("type")
        if not event_type:
            return

        if event_type == "StasisStart":
            await self._handle_stasis_start(event)
        elif event_type == "ChannelDestroyed":
            await self._handle_channel_destroyed(event)

    async def _handle_stasis_start(self, event: Dict[str, Any]):
        channel = event.get("channel", {})
        channel_id = channel.get("id")
        args = event.get("args", [])
        
        logger.info(f"StasisStart event for channel={channel_id}, args={args}")

        # Check if this is an ExternalMedia channel we created
        if channel.get("name", "").startswith("UnicastRTP"):
            logger.debug(f"Skipping StasisStart for ExternalMedia channel {channel_id}")
            return

        # Parse call_id from args
        call_id = None
        for arg in args:
            if arg.startswith("call_id:"):
                call_id = arg.split(":", 1)[1]
                break

        if not call_id:
            # This is an inbound call, create a new record
            from models.schemas import ScenarioType
            from services.scenario_service import SCENARIO_REGISTRY
            phone_number = channel.get("caller", {}).get("number", "unknown")
            
            # Map settings.DEFAULT_INBOUND_SCENARIO to ScenarioType enum
            try:
                inbound_scenario = ScenarioType(settings.DEFAULT_INBOUND_SCENARIO)
            except Exception:
                inbound_scenario = ScenarioType.APPOINTMENT_REMINDER
            
            # Use scenario's example_params as defaults so the greeting has real content
            default_params = SCENARIO_REGISTRY[inbound_scenario].example_params.copy()
                
            record = call_store.create(
                phone_number=phone_number,
                scenario_type=inbound_scenario,
                customer_name=settings.DEFAULT_CUSTOMER_NAME,
                custom_params=default_params
            )
            call_id = record.call_id
            logger.info(f"Created new call record for inbound call: {call_id}")

        # Register channel mappings
        self.channel_to_call_id[channel_id] = call_id
        
        call_record = call_store.get(call_id)
        if not call_record:
            logger.error(f"No call record found for call_id={call_id}")
            return
            
        call_store.update(call_id, status=CallStatus.IN_PROGRESS)

        # 1. Answer the call channel
        logger.info(f"Answering channel {channel_id} for call_id {call_id}")
        await self._send_command("POST", f"channels/{channel_id}/answer")
        
        # Wait a brief moment to ensure channel is fully established
        await asyncio.sleep(0.5)

        # 2. Allocate an RTP server session port
        try:
            rtp_port = await rtp_server.allocate_session(call_id)
        except Exception as e:
            logger.error(f"Failed to allocate RTP port: {e}")
            await self._send_command("DELETE", f"channels/{channel_id}")
            return

        # 3. Create ExternalMedia channel linking Asterisk to our RTP port
        external_host = f"127.0.0.1:{rtp_port}"
        logger.info(f"Creating ExternalMedia channel to {external_host}")
        
        external_media_params = {
            "app": self.app_name,
            "external_host": external_host,
            "format": "ulaw",
            "encapsulation": "rtp"
        }
        
        external_response = await self._send_command("POST", "channels/externalMedia", params=external_media_params)
        if not external_response or not external_response.get("id"):
            logger.error("Failed to create ExternalMedia channel")
            await rtp_server.cleanup_session(call_id)
            await self._send_command("DELETE", f"channels/{channel_id}")
            return
            
        external_channel_id = external_response["id"]
        logger.info(f"ExternalMedia channel created: {external_channel_id}")
        self.channel_to_call_id[external_channel_id] = call_id

        # Query Asterisk's local listening port and address for ExternalMedia to pre-establish remote endpoint
        try:
            var_port_res = await self._send_command(
                "GET", 
                f"channels/{external_channel_id}/variable", 
                params={"variable": "UNICASTRTP_LOCAL_PORT"}
            )
            var_host_res = await self._send_command(
                "GET", 
                f"channels/{external_channel_id}/variable", 
                params={"variable": "UNICASTRTP_LOCAL_ADDRESS"}
            )
            
            ast_rtp_port = None
            ast_rtp_host = "127.0.0.1"
            
            if var_port_res and var_port_res.get("value"):
                ast_rtp_port = int(var_port_res["value"])
            if var_host_res and var_host_res.get("value"):
                ast_rtp_host = var_host_res["value"]
                
            if ast_rtp_port:
                rtp_server.set_remote_endpoint(call_id, ast_rtp_host, ast_rtp_port)
        except Exception as e:
            logger.warning(f"Could not retrieve ExternalMedia local port from Asterisk ARI: {e}")

        # 4. Create a mixing bridge
        bridge_response = await self._send_command("POST", "bridges", params={"type": "mixing"})
        if not bridge_response or not bridge_response.get("id"):
            logger.error("Failed to create bridge")
            await self._send_command("DELETE", f"channels/{external_channel_id}")
            await rtp_server.cleanup_session(call_id)
            await self._send_command("DELETE", f"channels/{channel_id}")
            return
            
        bridge_id = bridge_response["id"]
        logger.info(f"Mixing bridge created: {bridge_id}")

        # 5. Add caller channel and ExternalMedia channel to bridge
        add_params = {"channel": f"{channel_id},{external_channel_id}"}
        await self._send_command("POST", f"bridges/{bridge_id}/addChannel", params=add_params)
        logger.info(f"Channels bridged: bridge={bridge_id}")

        # Save call info
        self.active_calls[call_id] = {
            "bridge_id": bridge_id,
            "caller_channel_id": channel_id,
            "external_media_channel_id": external_channel_id,
        }

        # 6. Initialize Custom AI Pipeline
        if not self.pipeline_class:
            from services.custom_pipeline import CustomPipeline
            self.pipeline_class = CustomPipeline

        pipeline = self.pipeline_class(call_id, call_record, rtp_server)
        self.active_calls[call_id]["pipeline"] = pipeline
        
        # Start pipeline tasks
        asyncio.create_task(pipeline.start())
        logger.info(f"AI Pipeline started for call_id={call_id}")

    async def _handle_channel_destroyed(self, event: Dict[str, Any]):
        channel = event.get("channel", {})
        channel_id = channel.get("id")
        
        call_id = self.channel_to_call_id.pop(channel_id, None)
        if not call_id:
            return
            
        logger.info(f"ChannelDestroyed for channel={channel_id}, associated call_id={call_id}")
        await self._cleanup_call(call_id, triggered_by_channel=channel_id)

    async def _cleanup_call(self, call_id: str, triggered_by_channel: Optional[str] = None):
        """Tear down all bridge and channel resources for a call."""
        call_info = self.active_calls.pop(call_id, None)
        if not call_info:
            return

        logger.info(f"Cleaning up call resources for call_id={call_id}")
        
        # Stop AI pipeline
        pipeline = call_info.get("pipeline")
        if pipeline:
            await pipeline.stop()

        # Stop RTP session
        await rtp_server.cleanup_session(call_id)

        # Destroy bridge
        bridge_id = call_info.get("bridge_id")
        if bridge_id:
            logger.info(f"Destroying bridge {bridge_id}")
            await self._send_command("DELETE", f"bridges/{bridge_id}")

        # Hang up external media channel
        external_channel_id = call_info.get("external_media_channel_id")
        if external_channel_id and external_channel_id != triggered_by_channel:
            logger.info(f"Hanging up ExternalMedia channel {external_channel_id}")
            await self._send_command("DELETE", f"channels/{external_channel_id}")

        # Hang up caller channel
        caller_channel_id = call_info.get("caller_channel_id")
        if caller_channel_id and caller_channel_id != triggered_by_channel:
            logger.info(f"Hanging up caller channel {caller_channel_id}")
            await self._send_command("DELETE", f"channels/{caller_channel_id}")

        # Update call store status and calculate duration
        call_record = call_store.get(call_id)
        if call_record:
            ended_at = datetime.now(timezone.utc)
            started_at = call_record.started_at
            if started_at.tzinfo is None:
                started_at = started_at.replace(tzinfo=timezone.utc)
            duration_seconds = int((ended_at - started_at).total_seconds())

            if call_record.status not in (CallStatus.COMPLETED, CallStatus.FAILED):
                call_store.update(
                    call_id,
                    status=CallStatus.COMPLETED,
                    ended_at=ended_at,
                    duration_seconds=duration_seconds
                )
            else:
                call_store.update(
                    call_id,
                    ended_at=ended_at,
                    duration_seconds=duration_seconds
                )
            
        logger.info(f"Call cleanup complete for call_id={call_id}")

# Singleton instance
asterisk_service = AsteriskService()
