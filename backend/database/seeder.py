"""
Database seeder - populate database with initial data
Run with: python backend/database/seeder.py
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database.db import init_db, get_db, SessionLocal
from database.models import Call
from datetime import datetime, timedelta
import json
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def seed_database():
    """Seed database with sample call records"""
    
    # Initialize tables
    init_db()
    
    db = SessionLocal()
    
    try:
        # Check if data already exists
        existing_count = db.query(Call).count()
        if existing_count > 0:
            logger.info(f"Database already has {existing_count} calls. Skipping seeding.")
            return
        
        logger.info("Starting database seeding...")
        
        # Sample calls data
        sample_calls = [
            {
                "call_id": "call_001_demo",
                "bot_name": "Alex",
                "bot_voice_id": "epkQ8pqDcY2DxhmFi8xl",
                "caller_number": "+1-555-0101",
                "caller_name": "Jawwad",
                "scenario_type": "appointment_reminder",
                "call_status": "completed",
                "recording_path": "./recordings/call_001_demo.wav",
                "conversation_history_path": "./recordings/call_001_demo_history.json",
                "transcript": "Agent: Hi Jawwad, this is a reminder about your appointment tomorrow at 2 PM.\nCaller: Yes, I'll be there.\nAgent: Great! See you then.",
                "duration_seconds": 45.0,
                "goal_achieved": True,
                "created_at": datetime.utcnow() - timedelta(days=2),
                "updated_at": datetime.utcnow() - timedelta(days=2),
                "started_at": datetime.utcnow() - timedelta(days=2),
                "ended_at": datetime.utcnow() - timedelta(days=2, hours=1),
            },
            {
                "call_id": "call_002_demo",
                "bot_name": "Alex",
                "bot_voice_id": "BIvP0GN1cAtSRTxNHnWS",
                "caller_number": "+1-555-0102",
                "caller_name": "John Smith",
                "scenario_type": "lead_qualification",
                "call_status": "completed",
                "recording_path": "./recordings/call_002_demo.wav",
                "conversation_history_path": "./recordings/call_002_demo_history.json",
                "transcript": "Agent: Hello, are you interested in our services?\nCaller: Tell me more.\nAgent: We offer premium solutions...",
                "duration_seconds": 120.0,
                "goal_achieved": True,
                "created_at": datetime.utcnow() - timedelta(days=1),
                "updated_at": datetime.utcnow() - timedelta(days=1),
                "started_at": datetime.utcnow() - timedelta(days=1),
                "ended_at": datetime.utcnow() - timedelta(days=1, hours=2),
            },
            {
                "call_id": "call_003_demo",
                "bot_name": "Alex",
                "bot_voice_id": "ljX1ZrXuDIIRVcmiVSyR",
                "caller_number": "+1-555-0103",
                "caller_name": "Sarah Johnson",
                "scenario_type": "customer_survey",
                "call_status": "completed",
                "recording_path": "./recordings/call_003_demo.wav",
                "conversation_history_path": "./recordings/call_003_demo_history.json",
                "transcript": "Agent: How satisfied are you with our service?\nCaller: Very satisfied!\nAgent: Thank you for your feedback.",
                "duration_seconds": 90.0,
                "goal_achieved": True,
                "created_at": datetime.utcnow() - timedelta(hours=12),
                "updated_at": datetime.utcnow() - timedelta(hours=12),
                "started_at": datetime.utcnow() - timedelta(hours=12),
                "ended_at": datetime.utcnow() - timedelta(hours=11, minutes=30),
            }
        ]
        
        # Insert sample calls
        for call_data in sample_calls:
            call = Call(**call_data)
            db.add(call)
            logger.info(f"Added call: {call_data['call_id']} - {call_data['caller_name']}")
        
        db.commit()
        logger.info(f"✅ Seeding complete! Added {len(sample_calls)} sample calls.")
        
    except Exception as e:
        db.rollback()
        logger.error(f"❌ Seeding failed: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    seed_database()
