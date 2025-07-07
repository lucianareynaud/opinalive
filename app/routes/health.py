"""
Health check and monitoring endpoints
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, text
from datetime import datetime
import logging
import asyncio
import os
from pathlib import Path

from ..database import get_db, engine
from ..config import settings

router = APIRouter()
logger = logging.getLogger(__name__)

@router.get("/")
async def health_check():
    """
    Basic health check endpoint
    """
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "version": "1.0.0",
        "environment": settings.ENVIRONMENT
    }

@router.get("/detailed")
async def detailed_health_check(db: Session = Depends(get_db)):
    """
    Detailed health check with all dependencies
    """
    health_status = {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "version": "1.0.0",
        "environment": settings.ENVIRONMENT,
        "checks": {}
    }
    
    # Database check
    try:
        result = await db.execute(text("SELECT 1"))
        health_status["checks"]["database"] = {
            "status": "healthy",
            "message": "Database connection successful"
        }
    except Exception as e:
        health_status["status"] = "unhealthy"
        health_status["checks"]["database"] = {
            "status": "unhealthy",
            "message": f"Database connection failed: {str(e)}"
        }
    
    # WhatsApp service check
    try:
        whatsapp_auth_dir = Path("./auth")
        if whatsapp_auth_dir.exists() and any(whatsapp_auth_dir.iterdir()):
            health_status["checks"]["whatsapp"] = {
                "status": "healthy",
                "message": "WhatsApp auth files present"
            }
        else:
            health_status["checks"]["whatsapp"] = {
                "status": "warning",
                "message": "WhatsApp not configured - QR scan required"
            }
    except Exception as e:
        health_status["checks"]["whatsapp"] = {
            "status": "unhealthy",
            "message": f"WhatsApp check failed: {str(e)}"
        }
    
    # OpenAI check
    health_status["checks"]["openai"] = {
        "status": "healthy" if settings.OPENAI_API_KEY and settings.OPENAI_API_KEY.startswith("sk-") else "unhealthy",
        "message": "API key configured" if settings.OPENAI_API_KEY else "API key missing"
    }
    
    # Environment variables check
    required_vars = ["DATABASE_URL", "OPENAI_API_KEY", "SECRET_KEY"]
    missing_vars = [var for var in required_vars if not getattr(settings, var, None)]
    
    if missing_vars:
        health_status["status"] = "unhealthy"
        health_status["checks"]["environment"] = {
            "status": "unhealthy",
            "message": f"Missing required variables: {', '.join(missing_vars)}"
        }
    else:
        health_status["checks"]["environment"] = {
            "status": "healthy",
            "message": "All required environment variables configured"
        }
    
    return health_status

@router.get("/ready")
async def readiness_check(db: Session = Depends(get_db)):
    """
    Kubernetes readiness probe
    """
    try:
        # Test database connection
        await db.execute(text("SELECT 1"))
        return {"status": "ready"}
    except Exception as e:
        raise HTTPException(status_code=503, detail="Service not ready")

@router.get("/live")
async def liveness_check():
    """
    Kubernetes liveness probe
    """
    return {"status": "alive"} 