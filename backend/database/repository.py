"""
Database service - high-level database operations for calls
"""

from sqlalchemy.orm import Session
from database.models import Call
from database.db import SessionLocal
from datetime import datetime
from typing import List, Optional
import json
import logging

logger = logging.getLogger(__name__)


class CallRepository:
    """Repository pattern for Call database operations"""
    
    @staticmethod
    def create(
        db: Session,
        call_id: str,
        bot_name: str,
        bot_voice_id: str,
        caller_number: str,
        caller_name: str,
        scenario_type: str,
        recording_path: Optional[str] = None,
        custom_params: Optional[dict] = None,
    ) -> Call:
        """Create a new call record"""
        try:
            call = Call(
                call_id=call_id,
                bot_name=bot_name,
                bot_voice_id=bot_voice_id,
                caller_number=caller_number,
                caller_name=caller_name,
                scenario_type=scenario_type,
                call_status="initiated",
                recording_path=recording_path,
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow(),
                custom_params=json.dumps(custom_params) if custom_params else None,
            )
            db.add(call)
            db.commit()
            db.refresh(call)
            logger.info(f"Created call record: {call_id}")
            return call
        except Exception as e:
            db.rollback()
            logger.error(f"Failed to create call record: {e}")
            raise
    
    @staticmethod
    def get_by_id(db: Session, call_id: str) -> Optional[Call]:
        """Get call by ID"""
        return db.query(Call).filter(Call.call_id == call_id).first()
    
    @staticmethod
    def get_all(db: Session, limit: int = 50, offset: int = 0) -> List[Call]:
        """Get all calls with pagination"""
        return db.query(Call).order_by(Call.created_at.desc()).limit(limit).offset(offset).all()
    
    @staticmethod
    def get_by_caller(db: Session, caller_number: str) -> List[Call]:
        """Get all calls for a specific caller"""
        return db.query(Call).filter(Call.caller_number == caller_number).order_by(Call.created_at.desc()).all()
    
    @staticmethod
    def get_by_scenario(db: Session, scenario_type: str) -> List[Call]:
        """Get all calls for a specific scenario"""
        return db.query(Call).filter(Call.scenario_type == scenario_type).order_by(Call.created_at.desc()).all()
    
    @staticmethod
    def update(
        db: Session,
        call_id: str,
        **kwargs
    ) -> Optional[Call]:
        """Update call record"""
        try:
            call = db.query(Call).filter(Call.call_id == call_id).first()
            if not call:
                logger.warning(f"Call not found: {call_id}")
                return None
            
            # Update fields
            for key, value in kwargs.items():
                if hasattr(call, key):
                    if key == "custom_params" and isinstance(value, dict):
                        value = json.dumps(value)
                    setattr(call, key, value)
            
            call.updated_at = datetime.utcnow()
            db.commit()
            db.refresh(call)
            logger.info(f"Updated call record: {call_id}")
            return call
        except Exception as e:
            db.rollback()
            logger.error(f"Failed to update call record: {e}")
            raise
    
    @staticmethod
    def update_transcript(db: Session, call_id: str, transcript: str) -> Optional[Call]:
        """Update call transcript"""
        return CallRepository.update(db, call_id, transcript=transcript)
    
    @staticmethod
    def update_conversation_history(db: Session, call_id: str, history: dict) -> Optional[Call]:
        """Update call conversation history"""
        return CallRepository.update(
            db,
            call_id,
            conversation_history=json.dumps(history) if isinstance(history, dict) else history
        )
    
    @staticmethod
    def update_status(db: Session, call_id: str, status: str) -> Optional[Call]:
        """Update call status"""
        return CallRepository.update(db, call_id, call_status=status)
    
    @staticmethod
    def complete_call(
        db: Session,
        call_id: str,
        duration_seconds: float,
        goal_achieved: bool,
        transcript: Optional[str] = None,
    ) -> Optional[Call]:
        """Mark call as completed"""
        return CallRepository.update(
            db,
            call_id,
            call_status="completed",
            ended_at=datetime.utcnow(),
            duration_seconds=duration_seconds,
            goal_achieved=goal_achieved,
            transcript=transcript,
        )
    
    @staticmethod
    def get_stats(db: Session) -> dict:
        """Get call statistics"""
        total = db.query(Call).count()
        completed = db.query(Call).filter(Call.call_status == "completed").count()
        failed = db.query(Call).filter(Call.call_status == "failed").count()
        
        return {
            "total_calls": total,
            "completed_calls": completed,
            "failed_calls": failed,
            "goal_achieved": db.query(Call).filter(Call.goal_achieved == True).count(),
        }


# Convenience functions
def get_call_db(call_id: str) -> Optional[Call]:
    """Get call from database"""
    db = SessionLocal()
    try:
        return CallRepository.get_by_id(db, call_id)
    finally:
        db.close()


def get_all_calls_db(limit: int = 50) -> List[Call]:
    """Get all calls from database"""
    db = SessionLocal()
    try:
        return CallRepository.get_all(db, limit=limit)
    finally:
        db.close()
