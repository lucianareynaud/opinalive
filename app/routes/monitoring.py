from fastapi import APIRouter, Response
from pydantic import BaseModel
from typing import Optional
from ..services.monitoring import MonitoringService

router = APIRouter()
monitoring = MonitoringService()

class WhatsAppStatus(BaseModel):
    status: str
    qr: Optional[str] = None
    reason: Optional[str] = None
    reconnect_count: Optional[int] = None
    phone: Optional[str] = None
    version: Optional[str] = None
    message_type: Optional[str] = None

class AudioProcessing(BaseModel):
    success: bool
    duration: float
    error: Optional[str] = None

@router.post("/whatsapp/status")
async def update_whatsapp_status(status: WhatsAppStatus):
    """
    Atualiza status do WhatsApp no monitoramento
    """
    extra_info = {k: v for k, v in status.dict().items() if k != 'status' and v is not None}
    monitoring.update_whatsapp_status(status.status, extra_info)
    return {"status": "updated"}

@router.post("/audio/processed")
async def record_audio_processing(processing: AudioProcessing):
    """
    Registra processamento de áudio no monitoramento
    """
    monitoring.record_audio_processing(
        success=processing.success,
        duration=processing.duration,
        error=processing.error
    )
    return {"status": "recorded"} 