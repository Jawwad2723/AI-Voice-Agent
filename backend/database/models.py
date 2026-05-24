"""
SQLAlchemy database models for voice AI agent
"""

from sqlalchemy import Column, String, DateTime, Text, Boolean, Float, create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from datetime import datetime
import json

Base = declarative_base()


class Call(Base):
    """Represents a single call in the system"""
    
    __tablename__ = "calls"
    
    # Primary identifiers
    call_id = Column(String(100), primary_key=True, index=True)
    
    # Bot and voice configuration
    bot_name = Column(String(255), nullable=False, default="Alex")
    bot_voice_id = Column(String(255), nullable=False)
    
    # Caller information
    caller_number = Column(String(50), nullable=False, index=True)
    caller_name = Column(String(255), default="Caller")
    
    # Call details
    scenario_type = Column(String(100), nullable=False)
    call_status = Column(String(50), nullable=False, default="initiated")  # initiated, ringing, in-progress, completed, failed
    
    # File paths
    recording_path = Column(Text, nullable=True)  # Path to .wav recording file
    conversation_history_path = Column(Text, nullable=True)  # Path to conversation JSON/TXT file
    
    # Conversation data (stored as JSON text)
    conversation_history = Column(Text, nullable=True)
    transcript = Column(Text, nullable=True)
    
    # Metadata
    duration_seconds = Column(Float, default=0.0)
    goal_achieved = Column(Boolean, default=False)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, index=True)
    started_at = Column(DateTime, nullable=True)
    ended_at = Column(DateTime, nullable=True)
    
    # Additional metadata
    notes = Column(Text, nullable=True)
    custom_params = Column(Text, nullable=True)  # JSON string
    
    def __repr__(self):
        return f"<Call(call_id={self.call_id}, caller={self.caller_number}, status={self.call_status})>"
    
    def to_dict(self):
        """Convert to dictionary for API responses"""
        return {
            "call_id": self.call_id,
            "bot_name": self.bot_name,
            "bot_voice_id": self.bot_voice_id,
            "caller_number": self.caller_number,
            "caller_name": self.caller_name,
            "scenario_type": self.scenario_type,
            "call_status": self.call_status,
            "recording_path": self.recording_path,
            "conversation_history_path": self.conversation_history_path,
            "conversation_history": self.conversation_history,
            "transcript": self.transcript,
            "duration_seconds": self.duration_seconds,
            "goal_achieved": self.goal_achieved,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "ended_at": self.ended_at.isoformat() if self.ended_at else None,
            "notes": self.notes,
            "custom_params": self.custom_params,
        }
