"""
Database calls router - API endpoints for accessing call history and statistics
"""

import logging
from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime

from database.db import get_db, SessionLocal
from database.repository import CallRepository
from database.models import Call
from pydantic import BaseModel

logger = logging.getLogger(__name__)
router = APIRouter()


# Pydantic schemas for API responses
class CallDetailResponse(BaseModel):
    call_id: str
    bot_name: str
    bot_voice_id: str
    caller_number: str
    caller_name: str
    scenario_type: str
    call_status: str
    recording_path: Optional[str] = None
    conversation_history_path: Optional[str] = None
    transcript: Optional[str] = None
    duration_seconds: float
    goal_achieved: bool
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    started_at: Optional[str] = None
    ended_at: Optional[str] = None
    
    class Config:
        from_attributes = True


class CallListResponse(BaseModel):
    total: int
    calls: List[CallDetailResponse]


class CallStatsResponse(BaseModel):
    total_calls: int
    completed_calls: int
    failed_calls: int
    goal_achieved: int


def get_db_safe() -> Optional[Session]:
    """Get database session safely, return None if unavailable"""
    try:
        db = get_db()
        if db is None:
            return None
        return db
    except Exception as e:
        logger.warning(f"Database session unavailable: {e}")
        return None


@router.get("/", response_model=CallListResponse)
async def list_all_calls(
    limit: int = 50,
    offset: int = 0,
):
    """Get all calls with pagination"""
    try:
        db = SessionLocal() if SessionLocal else None
        if db is None:
            raise HTTPException(
                status_code=503,
                detail="Database not available. Install psycopg2-binary: pip install psycopg2-binary"
            )
        
        calls = CallRepository.get_all(db, limit=limit, offset=offset)
        total = db.query(Call).count()
        db.close()
        
        return CallListResponse(
            total=total,
            calls=[CallDetailResponse.from_orm(c) for c in calls]
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error listing calls: {e}")
        raise HTTPException(status_code=500, detail="Failed to list calls")


@router.get("/{call_id}", response_model=CallDetailResponse)
async def get_call_detail(call_id: str):
    """Get specific call details"""
    try:
        db = SessionLocal() if SessionLocal else None
        if db is None:
            raise HTTPException(
                status_code=503,
                detail="Database not available. Install psycopg2-binary: pip install psycopg2-binary"
            )
        
        call = CallRepository.get_by_id(db, call_id)
        db.close()
        
        if not call:
            raise HTTPException(status_code=404, detail="Call not found")
        return CallDetailResponse.from_orm(call)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting call {call_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to get call details")


@router.get("/caller/{caller_number}")
async def get_calls_by_caller(caller_number: str):
    """Get all calls for a specific caller"""
    try:
        db = SessionLocal() if SessionLocal else None
        if db is None:
            raise HTTPException(
                status_code=503,
                detail="Database not available. Install psycopg2-binary: pip install psycopg2-binary"
            )
        
        calls = CallRepository.get_by_caller(db, caller_number)
        db.close()
        
        return {
            "caller_number": caller_number,
            "total": len(calls),
            "calls": [CallDetailResponse.from_orm(c) for c in calls]
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting calls for caller {caller_number}: {e}")
        raise HTTPException(status_code=500, detail="Failed to get caller calls")


@router.get("/scenario/{scenario_type}")
async def get_calls_by_scenario(scenario_type: str):
    """Get all calls for a specific scenario"""
    try:
        db = SessionLocal() if SessionLocal else None
        if db is None:
            raise HTTPException(
                status_code=503,
                detail="Database not available. Install psycopg2-binary: pip install psycopg2-binary"
            )
        
        calls = CallRepository.get_by_scenario(db, scenario_type)
        db.close()
        
        return {
            "scenario_type": scenario_type,
            "total": len(calls),
            "calls": [CallDetailResponse.from_orm(c) for c in calls]
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting calls for scenario {scenario_type}: {e}")
        raise HTTPException(status_code=500, detail="Failed to get scenario calls")


@router.get("/stats/overview")
async def get_call_stats():
    """Get call statistics"""
    try:
        db = SessionLocal() if SessionLocal else None
        if db is None:
            raise HTTPException(
                status_code=503,
                detail="Database not available. Install psycopg2-binary: pip install psycopg2-binary"
            )
        
        stats = CallRepository.get_stats(db)
        db.close()
        
        return stats
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting call stats: {e}")
        raise HTTPException(status_code=500, detail="Failed to get statistics")
