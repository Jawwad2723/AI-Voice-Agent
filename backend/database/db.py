"""
Database connection and session management
"""

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import NullPool
from config.settings import settings
from database.models import Base
import logging

logger = logging.getLogger(__name__)

# Create database engine - handle missing psycopg2 gracefully
engine = None
SessionLocal = None

try:
    engine = create_engine(
        settings.DATABASE_URL,
        echo=False,  # Set to True for SQL logging
        poolclass=NullPool,  # Avoid pool issues with async
    )
    
    # Session factory
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    logger.info("✅ Database engine created successfully")
except Exception as e:
    logger.warning(f"⚠️ Database engine creation failed: {e}")
    logger.warning("App will run without database persistence. Install psycopg2-binary: pip install psycopg2-binary")
    engine = None
    SessionLocal = None


def get_db() -> Session:
    """Get database session"""
    if SessionLocal is None:
        logger.error("Database not initialized. SessionLocal is None.")
        return None
    
    db = SessionLocal()
    try:
        return db
    except Exception as e:
        db.close()
        logger.error(f"Failed to get database session: {e}")
        raise


def close_db():
    """Close all connections"""
    if engine:
        engine.dispose()
        logger.info("Database connections closed")


def init_db():
    """Initialize database - create all tables"""
    if engine is None:
        logger.warning("Database engine not initialized. Skipping table creation.")
        return
    
    try:
        Base.metadata.create_all(bind=engine)
        logger.info("✅ Database tables created successfully")
    except Exception as e:
        logger.error(f"❌ Failed to create database tables: {e}")
        raise


def drop_all_tables():
    """Drop all tables - USE WITH CAUTION"""
    if engine is None:
        logger.warning("Database engine not initialized. Cannot drop tables.")
        return
    
    try:
        Base.metadata.drop_all(bind=engine)
        logger.warning("⚠️ All database tables dropped")
    except Exception as e:
        logger.error(f"❌ Failed to drop database tables: {e}")
        raise
