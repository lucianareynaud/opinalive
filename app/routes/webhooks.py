from fastapi import APIRouter, Request, BackgroundTasks, Depends, HTTPException
from sqlmodel import Session
from ..database import get_db
from ..services.whatsapp import WhatsAppService
from ..services.business import BusinessService
from ..services.usage import usage_service, UsageError, FeatureType
from ..services.transcription import TranscriptionService
from ..services.openai import OpenAIService
import logging
import base64
from pydantic import BaseModel, Field

router = APIRouter()
logger = logging.getLogger(__name__)

# Initialize services
whatsapp = WhatsAppService()
transcription = TranscriptionService()

def get_business_service(db: Session = Depends(get_db)) -> BusinessService:
    openai = OpenAIService()
    return BusinessService(db=db, openai=openai)

class AudioMessage(BaseModel):
    from_: str = Field(..., alias='from')
    message_id: str
    audio: str  # base64 encoded audio

class TestMessage(BaseModel):
    to_number: str
    message: str

@router.post("/test-message")
async def test_message(message: TestMessage):
    """
    Test endpoint to send WhatsApp messages
    """
    try:
        success = await whatsapp.send_text(message.to_number, message.message)
        if success:
            return {"status": "sent"}
        else:
            return {"status": "failed", "detail": "Failed to send message"}
    except Exception as e:
        logger.error(f"Error sending test message: {e}")
        return {"status": "error", "detail": str(e)}

@router.post("/process-audio")
async def process_audio(
    message: AudioMessage,
    background_tasks: BackgroundTasks,
    business_service: BusinessService = Depends(get_business_service),
    db: Session = Depends(get_db)
):
    """
    Process audio message received from WhatsApp
    """
    try:
        # Find user by phone number
        user = await business_service.find_user_by_phone(message.from_, db)
        if not user:
            logger.warning(f"No user found for phone {message.from_}")
            return {"status": "user not found"}
            
        # Check usage limits
        try:
            await usage_service.check_audio_limit(user, db)
            await usage_service.check_feature_access(user, FeatureType.BASIC_AI)
        except UsageError as e:
            logger.warning(f"Guardrail blocked processing: {e.detail}")
            return {"status": "limit exceeded", "reason": e.detail}
        
        # Decode audio from base64
        try:
            audio_bytes = base64.b64decode(message.audio)
        except Exception as e:
            logger.error(f"Failed to decode audio: {e}")
            return {"status": "invalid audio"}
        
        # Create response entry
        response = business_service.create_response_entry(
            link_id=user.active_link_id,  # Assuming user has an active link
            client_phone=message.from_,
            audio_url=message.message_id  # Store message ID as reference
        )
        
        if not response:
            logger.error("Failed to create response entry")
            return {"status": "failed to create response"}
        
        # Increment usage counters
        try:
            await usage_service.increment_audio_usage(user, db)
            await usage_service.increment_ai_usage(user, db, FeatureType.BASIC_AI)
        except Exception as e:
            logger.error(f"Error incrementing usage: {e}")
        
        # Process audio in background
        background_tasks.add_task(
            business_service.process_response,
            response.id,
            db,
            audio_bytes
        )
        
        logger.info(f"Created response {response.id} for user {user.id}")
        return {"status": "processing"}
        
    except Exception as e:
        logger.error(f"Error processing audio: {e}")
        return {"status": "error", "detail": str(e)}

# Não precisamos mais de rotas de webhook pois o Baileys
# salva os arquivos diretamente e processa via IPC 