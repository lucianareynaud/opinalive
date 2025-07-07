from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks, Form, UploadFile, File, Request
from sqlmodel import Session, select
from typing import List, Dict, Any, Optional
import uuid
import logging
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from ..database import get_db  # CORRIGIDO: era get_session, agora é get_db
from ..config import settings
import urllib.parse
from datetime import datetime

from ..models import User, ClientLink, ClientResponse, FeatureType
from ..services.storage import StorageService
from ..services.transcription import DeepgramService, TranscriptionService
from ..services.openai import OpenAIService
from ..services.whatsapp import WhatsAppService
from ..services.business import BusinessService
from ..services.usage import usage_service
from .auth import get_current_user  # CORRIGIDO: era get_current_tenant, agora é get_current_user

router = APIRouter()
logger = logging.getLogger(__name__)

# Initialize services
storage = StorageService()
deepgram = DeepgramService()
openai = OpenAIService()
whatsapp = WhatsAppService()
transcription_service = TranscriptionService()

@router.post("/request")
async def request_feedback(
    customer_phone: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)  # CORRIGIDO: era get_session
):
    """
    Send WhatsApp template requesting feedback
    """
    # Normalize phone number
    if not customer_phone.startswith("+"):
        customer_phone = f"+{customer_phone}"
    
    # Send template
    success = await whatsapp.send_template(customer_phone, current_user.name)  # CORRIGIDO: era tenant.name
    if not success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to send WhatsApp message"
        )
    
    return {"status": "sent"}

@router.get("/list")
async def list_feedback(
    current_user: User = Depends(get_current_user),  # CORRIGIDO: era tenant
    db: Session = Depends(get_db)  # CORRIGIDO: era get_session
) -> List[dict]:
    """
    List all feedback for user
    """
    # Buscar todas as respostas dos links do usuário
    feedbacks = db.exec(
        select(ClientResponse)
        .join(ClientLink)
        .where(ClientLink.user_id == current_user.id)
        .order_by(ClientResponse.created_at.desc())
    ).all()
    
    return [
        {
            "id": f.id,
            "client_name": f.client_name,
            "client_phone": f.client_phone,
            "audio_url": f.audio_url,
            "transcription": f.transcription,
            "sentiment": f.sentiment,
            "rating": f.rating,
            "processed": f.processed,
            "created_at": f.created_at.isoformat() if f.created_at else None
        }
        for f in feedbacks
    ]

@router.get("/stats")
async def get_feedback_stats(
    current_user: User = Depends(get_current_user),  # CORRIGIDO: era tenant
    db: Session = Depends(get_db)  # CORRIGIDO: era get_session
) -> dict:
    """
    Get comprehensive feedback statistics for user
    """
    business_service = BusinessService(db)
    stats = business_service.get_user_feedback_stats(current_user.id)  # CORRIGIDO: era tenant.id
    return stats

@router.get("/usage")
async def get_usage_summary(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> dict:
    """
    GUARDRAIL: Retorna resumo de uso atual e limites do plano
    """
    try:
        usage_summary = await usage_service.get_usage_summary(current_user, db)
        recommendations = await usage_service.get_upgrade_recommendations(current_user, db)
        
        return {
            "usage_summary": usage_summary,
            "recommendations": recommendations,
            "status": "success"
        }
    except Exception as e:
        logger.error(f"Erro ao obter resumo de uso: {e}")
        return {"status": "error", "detail": str(e)}

async def process_feedback(
    response_id: int,
    db: Session
):
    """
    Background task to process feedback
    """
    # Get feedback response
    response = db.get(ClientResponse, response_id)
    if not response or not response.audio_url:
        return
    
    # Transcribe
    transcription = await deepgram.transcribe_audio(response.audio_url)
    if not transcription:
        return
    
    # Analyze sentiment
    analysis = await openai.analyze_sentiment(transcription)
    
    # Update response
    response.transcription = transcription
    response.sentiment = analysis["sentiment"]
    response.processed = True
    
    db.add(response)
    db.commit()

@router.post("/process-webhook")
async def process_webhook(
    data: dict,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)  # CORRIGIDO: era get_session
):
    """
    Process WhatsApp webhook with audio
    """
    try:
        # Extract data
        changes = data["entry"][0]["changes"][0]
        value = changes["value"]
        
        if "messages" not in value:
            return {"status": "no message"}
        
        message = value["messages"][0]
        if message["type"] != "audio":
            return {"status": "not audio"}
        
        # Get audio and metadata
        audio_id = message["audio"]["id"]
        from_number = message["from"]
        
        # Download audio
        audio_bytes = await whatsapp.download_media(audio_id)
        if not audio_bytes:
            raise HTTPException(status_code=500, detail="Failed to download audio")
        
        # Upload to R2
        file_name = f"{uuid.uuid4()}.mp3"
        audio_url = await storage.upload_audio(audio_bytes, file_name)
        if not audio_url:
            raise HTTPException(status_code=500, detail="Failed to upload audio")
        
        # TODO: Implementar identificação automática do link via URL
        # Por enquanto, criar resposta genérica
        response = ClientResponse(
            link_id=1,  # TODO: Identificar link correto
            client_phone=from_number,
            audio_url=audio_url
        )
        db.add(response)
        db.commit()
        db.refresh(response)
        
        # Process in background
        background_tasks.add_task(process_feedback, response.id, db)
        
        return {"status": "processing"}
        
    except Exception as e:
        print(f"Error processing webhook: {e}")
        raise HTTPException(status_code=500, detail="Internal error")

@router.post("/links/create")
async def create_feedback_link(
    title: str,
    description: str = None,
    max_responses: int = None,
    expires_in_days: int = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Create a new feedback collection link
    """
    try:
        # Check if user can create more links
        await usage_service.check_feature_access(current_user, FeatureType.BASIC_AI)
        
        # Generate unique link ID
        link_id = str(uuid.uuid4())
        
        # Calculate expiration if provided
        expires_at = None
        if expires_in_days:
            from datetime import datetime, timedelta
            expires_at = datetime.utcnow() + timedelta(days=expires_in_days)
        
        # Create link
        link = ClientLink(
            user_id=current_user.id,
            link_id=link_id,
            title=title,
            description=description,
            max_responses=max_responses,
            expires_at=expires_at,
            is_active=True
        )
        
        db.add(link)
        db.commit()
        db.refresh(link)
        
        # Generate shareable URL
        share_url = f"{settings.BASE_URL}/f/{link_id}"
        
        return {
            "id": link.id,
            "link_id": link_id,
            "title": title,
            "description": description,
            "max_responses": max_responses,
            "expires_at": expires_at.isoformat() if expires_at else None,
            "share_url": share_url,
            "is_active": True,
            "created_at": link.created_at.isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error creating feedback link: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create feedback link"
        )

@router.get("/f/{link_id}")
async def handle_feedback_link(
    link_id: str,
    request: Request,
    db: Session = Depends(get_db)
):
    """
    Handle feedback link access - redirects to WhatsApp
    """
    try:
        # Find link
        link = db.exec(
            select(ClientLink)
            .where(
                ClientLink.link_id == link_id,
                ClientLink.is_active == True
            )
        ).first()
        
        if not link:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Link not found or inactive"
            )
            
        # Check if link expired
        if link.expires_at and datetime.utcnow() > link.expires_at:
            link.is_active = False
            db.add(link)
            db.commit()
            raise HTTPException(
                status_code=status.HTTP_410_GONE,
                detail="Link expired"
            )
            
        # Check max responses
        if link.max_responses and link.responses_count >= link.max_responses:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Maximum responses reached"
            )
            
        # Get user (owner of the link)
        user = db.exec(
            select(User).where(User.id == link.user_id)
        ).first()
        
        if not user or not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Link owner not found or inactive"
            )
            
        # Generate WhatsApp message
        whatsapp_message = f"Olá! {user.name} pediu seu feedback por áudio. Por favor, envie uma mensagem de voz com sua opinião."
        
        # Generate WhatsApp deep link
        whatsapp_number = settings.WHATSAPP_NUMBER
        whatsapp_url = f"https://wa.me/{whatsapp_number}?text={urllib.parse.quote(whatsapp_message)}"
        
        # Track view
        link.views_count = (link.views_count or 0) + 1
        db.add(link)
        db.commit()
        
        # Redirect to WhatsApp
        return RedirectResponse(whatsapp_url)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error handling feedback link: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to process feedback link"
        )

@router.post("/test-transcribe")
async def test_transcribe(
    audio: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    """
    Test endpoint for audio transcription
    """
    try:
        # Read audio file
        audio_bytes = await audio.read()
        
        # Transcribe audio
        transcription = await transcription_service.transcribe_audio(audio_bytes)
        
        # Analyze sentiment
        analysis = await openai.analyze_sentiment(transcription)
        
        return {
            "transcription": transcription,
            "sentiment": analysis["sentiment"],
            "summary": analysis["summary"]
        }
        
    except Exception as e:
        logger.error(f"Error in test transcription: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/process-audio/{link_id}")
async def process_audio(
    link_id: str,
    request: Request,
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Processa um áudio recebido via WhatsApp
    """
    try:
        # Busca o link e valida
        link = db.exec(select(ClientLink).where(ClientLink.link_id == link_id)).first()
        if not link:
            raise HTTPException(status_code=404, detail="Link não encontrado")
            
        # Extrai dados do request
        data = await request.json()
        audio_url = data.get("audio_url")
        client_identifier = data.get("client_identifier", "")  # Pode ser telefone, email, etc
        
        if not audio_url:
            raise HTTPException(status_code=400, detail="URL do áudio não fornecida")
            
        # Inicializa serviços
        openai_service = OpenAIService()
        transcription_service = TranscriptionService()
        business_service = BusinessService(db, openai_service)
        
        # Gera hash anônimo do cliente
        client_hash = openai_service.generate_client_hash(client_identifier, link.user_id)
        
        # Cria registro inicial
        response = ClientResponse(
            link_id=link.id,
            client_hash=client_hash,
            audio_url=audio_url,
            processed=False
        )
        db.add(response)
        await db.commit()
        await db.refresh(response)
        
        # Transcreve o áudio
        transcription = await transcription_service.transcribe_audio(audio_url)
        response.transcription = transcription
        
        # Processa o feedback
        await business_service.process_new_feedback(response)
        
        return {
            "status": "success",
            "message": "Áudio processado com sucesso",
            "data": {
                "transcription": transcription,
                "sentiment": response.sentiment,
                "rating": response.inferred_rating,
                "urgency": response.urgency,
                "key_phrases": response.key_phrases[:2],  # Retorna apenas 2 frases principais
                "action_items": response.action_items[:2]  # Retorna apenas 2 ações principais
            }
        }
        
    except Exception as e:
        logger.error(f"Erro ao processar áudio: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/dashboard/{user_id}")
async def get_dashboard(
    user_id: int,
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Retorna dados do dashboard para um usuário específico
    """
    try:
        # Valida usuário
        user = db.get(User, user_id)
        if not user:
            raise HTTPException(status_code=404, detail="Usuário não encontrado")
            
        # Inicializa serviços
        openai_service = OpenAIService()
        business_service = BusinessService(db, openai_service)
        
        # Busca dados do dashboard
        dashboard_data = await business_service.get_dashboard_data(user_id)
        return dashboard_data
        
    except Exception as e:
        logger.error(f"Erro ao buscar dashboard: {e}")
        raise HTTPException(status_code=500, detail=str(e)) 