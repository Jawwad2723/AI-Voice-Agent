"""
Silence detection and interaction service
Detects silence and triggers "Are you there?" prompt
"""

import asyncio
import logging
from typing import Callable, Optional
from datetime import datetime, timedelta
from config.settings import settings

logger = logging.getLogger(__name__)


class SilenceDetector:
    """Detects silence periods and triggers callbacks"""
    
    def __init__(self, timeout_seconds: float = 5.0, ask_prompt: bool = True):
        self.timeout_seconds = timeout_seconds or settings.SILENCE_TIMEOUT_SECONDS
        self.ask_prompt = ask_prompt or settings.ASK_ARE_YOU_THERE
        self.last_activity = datetime.utcnow()
        self.is_monitoring = False
        self.prompt_sent = False
        self.on_silence_callback: Optional[Callable] = None
    
    def activity_detected(self):
        """Called when activity is detected (caller speaks)"""
        self.last_activity = datetime.utcnow()
        self.prompt_sent = False  # Reset flag when activity resumes
        logger.debug("Activity detected, silence timer reset")
    
    def get_silence_duration(self) -> float:
        """Get current silence duration in seconds"""
        delta = datetime.utcnow() - self.last_activity
        return delta.total_seconds()
    
    def is_silent(self) -> bool:
        """Check if currently in silence"""
        return self.get_silence_duration() >= self.timeout_seconds
    
    async def start_monitoring(self, on_silence: Optional[Callable] = None):
        """Start monitoring for silence"""
        if on_silence:
            self.on_silence_callback = on_silence
        
        self.is_monitoring = True
        self.last_activity = datetime.utcnow()
        logger.info(f"Started silence monitoring (timeout: {self.timeout_seconds}s, ask_prompt: {self.ask_prompt})")
        
        # Monitor every 0.5 seconds
        while self.is_monitoring:
            try:
                if self.is_silent() and not self.prompt_sent:
                    if self.ask_prompt:
                        logger.info("Silence detected! Triggering 'Are you there?' prompt")
                        if self.on_silence_callback:
                            await self.on_silence_callback()
                        self.prompt_sent = True
                
                await asyncio.sleep(0.5)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in silence monitoring: {e}")
                await asyncio.sleep(1)
    
    def stop_monitoring(self):
        """Stop monitoring for silence"""
        self.is_monitoring = False
        logger.info("Stopped silence monitoring")
    
    def reset(self):
        """Reset silence detector"""
        self.last_activity = datetime.utcnow()
        self.prompt_sent = False


# Module-level instance
silence_detector = SilenceDetector()


async def handle_silence(agent_name: str = "Agent") -> str:
    """
    Generate response when silence is detected
    Returns the prompt to be spoken
    """
    prompt = f"Are you there? It seems like the line might have gone quiet. Please let me know if you can hear me."
    logger.info(f"Sending 'Are you there?' prompt from {agent_name}")
    return prompt
