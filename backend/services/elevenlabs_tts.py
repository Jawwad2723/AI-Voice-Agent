"""
ElevenLabs TTS service - with support for v2 and v3 models (emotions)
"""

import httpx
import logging
from typing import Optional
from config.settings import settings

logger = logging.getLogger(__name__)


class ElevenLabsService:
    """ElevenLabs TTS service with v2 and v3 model support"""
    
    BASE_URL = "https://api.elevenlabs.io"
    
    def __init__(self):
        self.api_key = settings.ELEVENLABS_API_KEY
        self.model = settings.LOCAL_ELEVENLABS_MODEL
        self.model_version = settings.ELEVENLABS_MODEL_VERSION
        self.headers = {
            "xi-api-key": self.api_key,
            "Content-Type": "application/json",
        }
    
    async def text_to_speech(
        self,
        text: str,
        voice_id: str,
        model_id: Optional[str] = None,
    ) -> bytes:
        """
        Convert text to speech using ElevenLabs v2 or v3
        
        Args:
            text: Text to convert to speech
            voice_id: Voice ID to use
            model_id: Optional model ID (defaults to settings.LOCAL_ELEVENLABS_MODEL)
        
        Returns:
            Audio bytes (MP3)
        """
        if not model_id:
            model_id = self.model
        
        payload = {
            "text": text,
            "model_id": model_id,
            "voice_settings": {
                "stability": 0.5,
                "similarity_boost": 0.75,
            }
        }
        
        # Add emotion settings for v3 model
        if self.model_version == "v3" and model_id.endswith("v3"):
            payload["voice_settings"]["style"] = 0.0
            payload["voice_settings"]["use_speaker_boost"] = True
        
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    f"{self.BASE_URL}/v1/text-to-speech/{voice_id}",
                    json=payload,
                    headers=self.headers,
                )
                response.raise_for_status()
                return response.content
        except Exception as e:
            logger.error(f"ElevenLabs TTS error: {e}")
            raise
    
    async def get_voices(self) -> dict:
        """Get available voices"""
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                response = await client.get(
                    f"{self.BASE_URL}/v1/voices",
                    headers=self.headers,
                )
                response.raise_for_status()
                return response.json()
        except Exception as e:
            logger.error(f"Failed to get ElevenLabs voices: {e}")
            raise


# Module-level singleton
elevenlabs_service = ElevenLabsService()
