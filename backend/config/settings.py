"""
Application settings using pydantic-settings
"""

from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    # Vapi Configuration (Retained for compatibility)
    VAPI_API_KEY: str = ""
    VAPI_PHONE_NUMBER_ID: str = ""

    # Webhook URL (ngrok or production URL)
    WEBHOOK_BASE_URL: str = "https://your-ngrok-url.ngrok.io"

    # Optional: Fallback LLM key if using custom pipeline
    OPENAI_API_KEY: Optional[str] = None

    # Asterisk ARI Configuration
    ASTERISK_HOST: str = "127.0.0.1"
    ASTERISK_PORT: int = 8088
    ASTERISK_ARI_USERNAME: str = "ariuser"
    ASTERISK_ARI_PASSWORD: str = "aripassword"
    ASTERISK_ARI_APP: str = "asterisk-ai-voice-agent"
    ASTERISK_OUTBOUND_ENDPOINT_FORMAT: str = "PJSIP/{phone_number}"

    # Custom Pipeline Configurations
    DEEPGRAM_API_KEY: str = ""
    
    # LLM Configuration (Qwen or OpenAI)
    LLM_PROVIDER: str = "qwen"  # "qwen" or "openai"
    OLLAMA_BASE_URL: str = "http://38.247.189.107:8095/v1"
    QWEN_CHAT_MODEL: str = "Qwen/Qwen2.5-7B-Instruct-AWQ"
    OLLAMA_API_KEY: str = "mykey"
    
    ELEVENLABS_API_KEY: str = ""
    LOCAL_ELEVENLABS_VOICE_ID: str = "J2FGlQG8Gd7x8uEDt2H8"
    LOCAL_ELEVENLABS_MODEL: str = "eleven_multilingual_v2"  # Can use v3 for emotions
    ELEVENLABS_MODEL_VERSION: str = "v2"  # "v2" or "v3" for emotions support

    # Scenario Specific Voice IDs
    VOICE_APPOINTMENT_REMINDER: str = "epkQ8pqDcY2DxhmFi8xl"
    VOICE_LEAD_QUALIFICATION: str = "BIvP0GN1cAtSRTxNHnWS"
    VOICE_CUSTOMER_SURVEY: str = "ljX1ZrXuDIIRVcmiVSyR"
    VOICE_PAYMENT_FOLLOWUP: str = "bMxLr8fP6hzNRRi9nJxU"
    VOICE_EVENT_CONFIRMATION: str = "J2FGlQG8Gd7x8uEDt2H8"

    def get_voice_id(self, scenario_type: str) -> str:
        # Standardize matching
        s = scenario_type.lower().replace("-", "_")
        if s == "appointment_reminder":
            return self.VOICE_APPOINTMENT_REMINDER
        elif s == "lead_qualification":
            return self.VOICE_LEAD_QUALIFICATION
        elif s == "customer_survey":
            return self.VOICE_CUSTOMER_SURVEY
        elif s == "payment_followup":
            return self.VOICE_PAYMENT_FOLLOWUP
        elif s == "event_confirmation":
            return self.VOICE_EVENT_CONFIRMATION
        return self.LOCAL_ELEVENLABS_VOICE_ID

    # Agent Configuration
    AGENT_NAME: str = "Alex"  # Controllable via env
    DEFAULT_CUSTOMER_NAME: str = "Jawwad"  # Changed from "Inbound Caller"

    # Silence & Interaction Features
    SILENCE_TIMEOUT_SECONDS: float = 5.0  # Trigger "Are you there?" after 5 seconds
    ASK_ARE_YOU_THERE: bool = True  # Enable/disable the "Are you there?" prompt

    # Database Configuration
    DATABASE_URL: str = "postgresql+psycopg2://user:password@localhost/voiceai"  # Override with env
    
    # Recording Configuration
    RECORDING_DIR: str = "./recordings"  # Path to store .wav recordings
    # RTP Server Configuration
    RTP_SERVER_HOST: str = "0.0.0.0"
    RTP_PORT_RANGE_START: int = 18080
    RTP_PORT_RANGE_END: int = 18180
    # RTP Server Configuration
    RTP_SERVER_HOST: str = "0.0.0.0"
    RTP_PORT_RANGE_START: int = 18080
    RTP_PORT_RANGE_END: int = 18180

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"


settings = Settings()
