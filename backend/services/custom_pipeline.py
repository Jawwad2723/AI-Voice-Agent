import asyncio
import httpx
import websockets
import json
import logging
import audioop
from typing import List, Dict, Any, Optional

from config.settings import settings
from services.scenario_service import _build_system_prompt, _build_first_message
from services.call_store import call_store

logger = logging.getLogger(__name__)

class CustomPipeline:
    def __init__(self, call_id: str, call_record: Any, rtp_server: Any):
        self.call_id = call_id
        self.call_record = call_record
        self.rtp_server = rtp_server
        
        self.deepgram_ws = None
        self.running = False
        
        self.conversation_history: List[Dict[str, str]] = []
        self.system_prompt = ""
        self.first_message = ""
        
        self.current_transcript = ""
        self.user_speaking = False
        self.silence_frames = 0
        
        # VAD Parameters
        self.speech_frames_threshold = 2
        self.silence_frames_threshold = 40  # 40 frames * 20ms = 800ms
        self.rms_threshold = 600            # Energy threshold for speech detection
        
        # Audio transmission queue
        self.audio_queue = asyncio.Queue()
        
        # Playout control
        self.current_playback_task: Optional[asyncio.Task] = None
        self.deepgram_task: Optional[asyncio.Task] = None
        self.stt_sender_task: Optional[asyncio.Task] = None
        self.llm_lock = asyncio.Lock()
        self.received_count = 0
        self.conversation_silence_frames = 0
        self.asked_are_you_there = False
        
    async def start(self):
        self.running = True
        
        # Build prompt & first message using existing scenario service
        self.system_prompt = _build_system_prompt(
            self.call_record.scenario_type,
            self.call_record.customer_name,
            self.call_record.custom_params
        )
        self.first_message = _build_first_message(
            self.call_record.scenario_type,
            self.call_record.customer_name,
            self.call_record.custom_params
        )
        
        self.conversation_history = [
            {"role": "system", "content": self.system_prompt},
            {"role": "assistant", "content": self.first_message}
        ]
        
        # Store greeting in transcript
        try:
            call_store.update(self.call_id, transcript=f"Agent: {self.first_message}")
        except Exception as e:
            logger.error(f"Failed to store greeting in transcript: {e}")
        
        # Start the queue sender task
        self.stt_sender_task = asyncio.create_task(self._stt_sender_loop())
        
        # Connect to Deepgram STT
        await self._connect_deepgram()
        
        # Set RTP receiver callback (greeting will be spoken after first RTP packet)
        self.greeting_spoken = False
        self.rtp_server.set_audio_callback(self.call_id, self._on_audio_received)
        
        logger.info(f"Pipeline ready. Waiting for first RTP packet before speaking greeting.")

    async def stop(self):
        self.running = False
        self.rtp_server.remove_audio_callback(self.call_id)
        
        if self.current_playback_task:
            self.current_playback_task.cancel()
            
        if self.deepgram_task:
            self.deepgram_task.cancel()
            
        if self.stt_sender_task:
            self.stt_sender_task.cancel()
            
        if self.deepgram_ws:
            try:
                await self.deepgram_ws.close()
            except Exception:
                pass
                
        logger.info(f"CustomPipeline stopped for call_id={self.call_id}")

    async def _connect_deepgram(self):
        url = "wss://api.deepgram.com/v1/listen?model=nova-2&encoding=mulaw&sample_rate=8000&channels=1&interim_results=false"
        headers = {
            "Authorization": f"Token {settings.DEEPGRAM_API_KEY}"
        }
        try:
            # Support both old and new versions of websockets library
            import inspect
            kwargs = {}
            sig = inspect.signature(websockets.connect)
            if "additional_headers" in sig.parameters:
                kwargs["additional_headers"] = headers
            else:
                kwargs["extra_headers"] = headers

            self.deepgram_ws = await websockets.connect(url, **kwargs)
            self.deepgram_task = asyncio.create_task(self._deepgram_receive_loop())
            logger.info("Connected to Deepgram STT WebSocket")
        except Exception as e:
            logger.error(f"Failed to connect to Deepgram STT: {e}")
            raise

    async def _stt_sender_loop(self):
        """Read audio frames from the queue and stream them to Deepgram WebSocket."""
        logger.info("STT sender loop started")
        sent_count = 0
        pop_count = 0
        try:
            while self.running:
                try:
                    data = await self.audio_queue.get()
                    pop_count += 1
                    if pop_count % 50 == 0:
                        ws_status = "initialized" if self.deepgram_ws else "None"
                        logger.info(f"STT loop telemetry: popped {pop_count} frames, ws_status={ws_status}, queue_size={self.audio_queue.qsize()}")

                    if self.deepgram_ws:
                        try:
                            await self.deepgram_ws.send(data)
                            sent_count += 1
                            if sent_count % 50 == 0:
                                logger.info(f"Streamed {sent_count} audio frames to Deepgram")
                        except Exception as e:
                            logger.error(f"Error sending audio to Deepgram: {e}")
                            await asyncio.sleep(0.02)
                            self.audio_queue.put_nowait(data)
                    else:
                        # Wait and put back in queue if websocket is not initialized yet
                        await asyncio.sleep(0.02)
                        self.audio_queue.put_nowait(data)
                except Exception as inner_e:
                    logger.exception(f"Error in STT sender loop iteration: {inner_e}")
                    await asyncio.sleep(0.1)
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.exception(f"STT sender loop crashed: {e}")

    async def _deepgram_receive_loop(self):
        """Receive transcripts from Deepgram WebSocket."""
        try:
            async for message in self.deepgram_ws:
                logger.info(f"Deepgram raw message: {message}")
                data = json.loads(message)
                if data.get("type") == "Results":
                    channel = data.get("channel", {})
                    alternatives = channel.get("alternatives", [])
                    speech_final = data.get("speech_final", False)
                    if alternatives:
                        transcript = alternatives[0].get("transcript", "").strip()
                        is_final = data.get("is_final", False)
                        if transcript:
                            logger.info(f"Deepgram transcript (is_final={is_final}, speech_final={speech_final}): '{transcript}'")
                            if self.current_transcript:
                                self.current_transcript += " " + transcript
                            else:
                                self.current_transcript = transcript
                        
                        # Trigger LLM turn when Deepgram says the user is done speaking
                        if speech_final and self.current_transcript.strip():
                            logger.info(f"speech_final=True with transcript '{self.current_transcript}' — triggering LLM")
                            asyncio.create_task(self._process_user_turn())
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error(f"Deepgram receive loop error: {e}")

    def _on_audio_received(self, data: bytes):
        """RTP callback for incoming caller audio."""
        if not self.running:
            return
        
        # Speak greeting once remote endpoint is established (first RTP packet)
        if not self.greeting_spoken:
            self.greeting_spoken = True
            logger.info(f"First RTP packet received. Speaking greeting: '{self.first_message}'")
            asyncio.create_task(self._speak(self.first_message))
            
        # Decode and compute RMS
        try:
            pcm = audioop.ulaw2lin(data, 2)
            rms = audioop.rms(pcm, 2)
        except Exception as e:
            logger.warning(f"Error measuring audio frame RMS: {e}")
            rms = 0

        # Queue audio for streaming to Deepgram
        self.audio_queue.put_nowait(data)
        
        self.received_count += 1
        if self.received_count % 50 == 0:
            logger.info(f"RTP telemetry: received {self.received_count} frames from Asterisk (last RMS={rms}), queue size={self.audio_queue.qsize()}")

        # VAD & Barge-in / Silence logic
        if rms >= self.rms_threshold:
            self.silence_frames = 0
            self.conversation_silence_frames = 0
            self.asked_are_you_there = False
            if not self.user_speaking:
                self.user_speaking = True
                logger.info(f"VAD: User started speaking (RMS={rms})")
                # Barge-in: interrupt AI speech
                self._interrupt_playback()
        else:
            if self.user_speaking:
                self.silence_frames += 1
                if self.silence_frames >= self.silence_frames_threshold:
                    self.user_speaking = False
                    logger.info("VAD: User finished speaking (waiting for Deepgram speech_final)")
                    # NOTE: LLM is now triggered by speech_final from Deepgram, not here
            else:
                # Overall conversation silence tracking (when neither user nor AI is speaking)
                is_ai_speaking = self.current_playback_task is not None and not self.current_playback_task.done()
                if is_ai_speaking:
                    self.conversation_silence_frames = 0
                else:
                    self.conversation_silence_frames += 1
                    if self.conversation_silence_frames >= 250:  # 250 frames * 20ms = 5 seconds
                        self.conversation_silence_frames = 0
                        if not self.asked_are_you_there:
                            self.asked_are_you_there = True
                            logger.info("Silence detected for 5 seconds. Asking 'Are you there?'")
                            
                            self.conversation_history.append({"role": "assistant", "content": "Are you there?"})
                            try:
                                record = call_store.get(self.call_id)
                                if record:
                                    full_transcript = record.transcript or ""
                                    new_transcript = f"{full_transcript}\nAgent: Are you there?".strip()
                                    call_store.update(self.call_id, transcript=new_transcript)
                            except Exception as e:
                                logger.error(f"Failed to update transcript: {e}")
                                
                            asyncio.create_task(self._speak("Are you there?"))
                        else:
                            logger.info("Silence detected for another 5 seconds after asking. Hanging up call.")
                            from services.asterisk_service import asterisk_service
                            asyncio.create_task(asterisk_service._cleanup_call(self.call_id))

    def _interrupt_playback(self):
        if self.current_playback_task and not self.current_playback_task.done():
            logger.info("Barge-in! Interrupting AI speech playback.")
            self.current_playback_task.cancel()
            self.current_playback_task = None

    async def _process_user_turn(self):
        """Processes the turn once the user stops speaking."""
        async with self.llm_lock:
            # Wait a tiny bit (200ms) for any final transcripts to arrive from Deepgram
            await asyncio.sleep(0.2)
            
            transcript = self.current_transcript.strip()
            self.current_transcript = "" # Reset transcript for next turn
            
            if not transcript:
                logger.info("Turn ended, but transcript was empty. Skipping LLM.")
                return
                
            logger.info(f"Processing LLM response for user input: '{transcript}'")
            
            # Update transcript in CallStore
            try:
                record = call_store.get(self.call_id)
                if record:
                    full_transcript = record.transcript or ""
                    new_transcript = f"{full_transcript}\nUser: {transcript}".strip()
                    call_store.update(self.call_id, transcript=new_transcript)
            except Exception as e:
                logger.error(f"Failed to update transcript in store: {e}")
            
            self.conversation_history.append({"role": "user", "content": transcript})
            
            try:
                response_text = await self._get_llm_response()
                logger.info(f"Qwen LLM response: '{response_text}'")
                
                # Update transcript in CallStore with assistant response
                try:
                    record = call_store.get(self.call_id)
                    if record:
                        full_transcript = record.transcript or ""
                        new_transcript = f"{full_transcript}\nAgent: {response_text}".strip()
                        call_store.update(self.call_id, transcript=new_transcript)
                except Exception as e:
                    logger.error(f"Failed to update transcript in store: {e}")

                self.conversation_history.append({"role": "assistant", "content": response_text})
                
                # Speak response
                await self._speak(response_text)
                
            except Exception as e:
                logger.error(f"Error processing LLM turn: {e}")

    async def _get_llm_response(self) -> str:
        """Calls the self-hosted Ollama Qwen API."""
        url = f"{settings.OLLAMA_BASE_URL}/chat/completions"
        headers = {
            "Authorization": f"Bearer {settings.OLLAMA_API_KEY}",
            "Content-Type": "application/json"
        }
        payload = {
            "model": settings.QWEN_CHAT_MODEL,
            "messages": self.conversation_history,
            "temperature": 0.7
        }
        
        async with httpx.AsyncClient() as client:
            response = await client.post(url, headers=headers, json=payload, timeout=30.0)
            response.raise_for_status()
            data = response.json()
            return data["choices"][0]["message"]["content"].strip()

    async def _speak(self, text: str):
        # Cancel any active playback
        self._interrupt_playback()
        
        # Start new playback task
        self.current_playback_task = asyncio.create_task(self._playback_loop(text))
        try:
            await self.current_playback_task
        except asyncio.CancelledError:
            pass

    async def _playback_loop(self, text: str):
        """Stream TTS audio from ElevenLabs to RTP in real-time."""
        try:
            await self.rtp_server.stream_audio(self.call_id, self._stream_tts(text))
        except asyncio.CancelledError:
            raise
        except Exception as e:
            logger.error(f"Error in TTS streaming playback loop: {e}")

    async def _stream_tts(self, text: str):
        """Async generator that yields ulaw audio chunks from ElevenLabs as they arrive."""
        voice_id = settings.get_voice_id(self.call_record.scenario_type.value)
        url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}/stream"
        params = {"output_format": "ulaw_8000"}
        headers = {
            "xi-api-key": settings.ELEVENLABS_API_KEY,
            "Content-Type": "application/json"
        }
        payload = {
            "text": text,
            "model_id": settings.LOCAL_ELEVENLABS_MODEL,
            "voice_settings": {
                "stability": 0.45,
                "similarity_boost": 0.80,
                "style": 0.35,
                "use_speaker_boost": True
            }
        }
        try:
            async with httpx.AsyncClient() as client:
                async with client.stream(
                    "POST", url, headers=headers, params=params, json=payload, timeout=30.0
                ) as response:
                    response.raise_for_status()
                    logger.info(f"ElevenLabs streaming TTS started for: '{text[:60]}...'" if len(text) > 60 else f"ElevenLabs streaming TTS started for: '{text}'")
                    async for chunk in response.aiter_bytes(chunk_size=320):  # ~40ms per fetch
                        if chunk:
                            yield chunk
        except asyncio.CancelledError:
            raise
        except Exception as e:
            logger.error(f"ElevenLabs streaming TTS failed: {e}")
