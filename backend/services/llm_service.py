"""
LLM service - abstraction layer for multiple LLM providers (Qwen, OpenAI)
"""

import logging
from typing import List, Dict, Any, Optional
from abc import ABC, abstractmethod
import httpx
from config.settings import settings

logger = logging.getLogger(__name__)


class LLMProvider(ABC):
    """Abstract base class for LLM providers"""
    
    @abstractmethod
    async def generate_response(
        self,
        messages: List[Dict[str, str]],
        **kwargs
    ) -> str:
        """Generate a response from the LLM"""
        pass


class QwenProvider(LLMProvider):
    """Qwen LLM provider using Ollama backend"""
    
    def __init__(self):
        self.base_url = settings.OLLAMA_BASE_URL
        self.model = settings.QWEN_CHAT_MODEL
        self.api_key = settings.OLLAMA_API_KEY
    
    async def generate_response(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int = 500,
        **kwargs
    ) -> str:
        """Generate response using Qwen via Ollama"""
        try:
            payload = {
                "model": self.model,
                "messages": messages,
                "temperature": temperature,
                "max_tokens": max_tokens,
                "stream": False,
            }
            
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            }
            
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    f"{self.base_url}/chat/completions",
                    json=payload,
                    headers=headers,
                )
                response.raise_for_status()
                data = response.json()
                
                # Extract response text
                if "choices" in data and len(data["choices"]) > 0:
                    return data["choices"][0]["message"]["content"]
                else:
                    raise ValueError("Unexpected response format from Qwen")
                    
        except Exception as e:
            logger.error(f"Qwen API error: {e}")
            raise


class OpenAIProvider(LLMProvider):
    """OpenAI LLM provider"""
    
    def __init__(self):
        self.api_key = settings.OPENAI_API_KEY
        if not self.api_key:
            raise ValueError("OPENAI_API_KEY not configured")
    
    async def generate_response(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int = 500,
        model: str = "gpt-3.5-turbo",
        **kwargs
    ) -> str:
        """Generate response using OpenAI"""
        try:
            payload = {
                "model": model,
                "messages": messages,
                "temperature": temperature,
                "max_tokens": max_tokens,
            }
            
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            }
            
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    "https://api.openai.com/v1/chat/completions",
                    json=payload,
                    headers=headers,
                )
                response.raise_for_status()
                data = response.json()
                
                # Extract response text
                if "choices" in data and len(data["choices"]) > 0:
                    return data["choices"][0]["message"]["content"]
                else:
                    raise ValueError("Unexpected response format from OpenAI")
                    
        except Exception as e:
            logger.error(f"OpenAI API error: {e}")
            raise


class LLMService:
    """Factory and facade for LLM operations"""
    
    def __init__(self):
        self.provider = self._get_provider()
    
    def _get_provider(self) -> LLMProvider:
        """Get LLM provider based on settings"""
        provider_name = settings.LLM_PROVIDER.lower()
        
        if provider_name == "openai":
            logger.info("Using OpenAI as LLM provider")
            return OpenAIProvider()
        elif provider_name == "qwen":
            logger.info("Using Qwen as LLM provider")
            return QwenProvider()
        else:
            logger.warning(f"Unknown LLM provider: {provider_name}, defaulting to Qwen")
            return QwenProvider()
    
    async def generate_response(
        self,
        messages: List[Dict[str, str]],
        **kwargs
    ) -> str:
        """Generate a response from the configured LLM"""
        return await self.provider.generate_response(messages, **kwargs)


# Module-level singleton
llm_service = LLMService()
