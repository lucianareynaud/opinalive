from prometheus_client import Counter, Gauge, Histogram
import structlog
from datetime import datetime, timezone
import json
from typing import Dict, Any
from pathlib import Path

logger = structlog.get_logger()

# Métricas do WhatsApp
whatsapp_connection_status = Gauge(
    'whatsapp_connection_status',
    'Status da conexão do WhatsApp (1=conectado, 0=desconectado)'
)

whatsapp_last_message = Gauge(
    'whatsapp_last_message_timestamp',
    'Timestamp da última mensagem recebida'
)

whatsapp_reconnect_count = Counter(
    'whatsapp_reconnect_total',
    'Número total de reconexões do WhatsApp'
)

# Métricas de processamento
audio_processing_total = Counter(
    'audio_processing_total',
    'Total de áudios processados',
    ['status']  # success, error
)

audio_processing_duration = Histogram(
    'audio_processing_duration_seconds',
    'Tempo de processamento de áudio',
    buckets=[1, 5, 10, 30, 60, 120]  # buckets em segundos
)

transcription_errors = Counter(
    'transcription_errors_total',
    'Total de erros de transcrição',
    ['error_type']
)

class MonitoringService:
    def __init__(self):
        self.health_file = Path("health_status.json")
        self._load_health_status()

    def _load_health_status(self):
        """Carrega o status de saúde do arquivo"""
        if self.health_file.exists():
            try:
                with open(self.health_file) as f:
                    self.health_status = json.load(f)
            except:
                self.health_status = self._create_initial_health()
        else:
            self.health_status = self._create_initial_health()
        
        self._save_health_status()

    def _create_initial_health(self) -> Dict[str, Any]:
        """Cria estrutura inicial do status de saúde"""
        return {
            "whatsapp": {
                "last_connected": None,
                "last_disconnected": None,
                "last_message_received": None,
                "total_reconnects": 0,
                "connection_status": "unknown",
                "last_qr_code_shown": None
            },
            "processing": {
                "total_audios": 0,
                "successful_audios": 0,
                "failed_audios": 0,
                "last_successful_processing": None,
                "last_error": None,
                "last_error_time": None
            },
            "system": {
                "start_time": datetime.now(timezone.utc).isoformat(),
                "last_update": datetime.now(timezone.utc).isoformat()
            }
        }

    def _save_health_status(self):
        """Salva o status de saúde em arquivo"""
        self.health_status["system"]["last_update"] = datetime.now(timezone.utc).isoformat()
        with open(self.health_file, 'w') as f:
            json.dump(self.health_status, f, indent=2)

    def update_whatsapp_status(self, status: str, extra_info: Dict[str, Any] = None):
        """Atualiza status do WhatsApp"""
        now = datetime.now(timezone.utc)
        
        if status == "connected":
            self.health_status["whatsapp"]["last_connected"] = now.isoformat()
            self.health_status["whatsapp"]["connection_status"] = "connected"
            whatsapp_connection_status.set(1)
            
        elif status == "disconnected":
            self.health_status["whatsapp"]["last_disconnected"] = now.isoformat()
            self.health_status["whatsapp"]["connection_status"] = "disconnected"
            whatsapp_connection_status.set(0)
            
        elif status == "qr_code":
            self.health_status["whatsapp"]["last_qr_code_shown"] = now.isoformat()
            self.health_status["whatsapp"]["connection_status"] = "waiting_qr"
            
        if extra_info:
            self.health_status["whatsapp"].update(extra_info)
            
        if "reconnect_count" in (extra_info or {}):
            self.health_status["whatsapp"]["total_reconnects"] = extra_info["reconnect_count"]
            whatsapp_reconnect_count.inc()
            
        self._save_health_status()
        
        # Log estruturado
        logger.info(
            "whatsapp_status_update",
            status=status,
            **self.health_status["whatsapp"]
        )

    def record_message_received(self):
        """Registra recebimento de mensagem"""
        now = datetime.now(timezone.utc)
        self.health_status["whatsapp"]["last_message_received"] = now.isoformat()
        whatsapp_last_message.set(now.timestamp())
        self._save_health_status()

    def record_audio_processing(self, success: bool, duration: float = None, error: str = None):
        """Registra processamento de áudio"""
        now = datetime.now(timezone.utc)
        
        self.health_status["processing"]["total_audios"] += 1
        if success:
            self.health_status["processing"]["successful_audios"] += 1
            self.health_status["processing"]["last_successful_processing"] = now.isoformat()
            audio_processing_total.labels(status="success").inc()
        else:
            self.health_status["processing"]["failed_audios"] += 1
            self.health_status["processing"]["last_error"] = error
            self.health_status["processing"]["last_error_time"] = now.isoformat()
            audio_processing_total.labels(status="error").inc()
            
        if duration:
            audio_processing_duration.observe(duration)
            
        self._save_health_status()
        
        # Log estruturado
        logger.info(
            "audio_processing_recorded",
            success=success,
            duration=duration,
            error=error,
            **self.health_status["processing"]
        )

    def get_health_check(self) -> Dict[str, Any]:
        """Retorna status completo de saúde do sistema"""
        now = datetime.now(timezone.utc)
        
        # Calcula status geral
        whatsapp_ok = (
            self.health_status["whatsapp"]["connection_status"] == "connected" and
            self.health_status["whatsapp"].get("last_message_received") and
            (now - datetime.fromisoformat(self.health_status["whatsapp"]["last_message_received"])).total_seconds() < 3600
        )
        
        processing_ok = (
            self.health_status["processing"]["total_audios"] > 0 and
            (self.health_status["processing"]["failed_audios"] / self.health_status["processing"]["total_audios"]) < 0.3
        )
        
        status = {
            "status": "healthy" if whatsapp_ok and processing_ok else "unhealthy",
            "whatsapp_connection": self.health_status["whatsapp"]["connection_status"],
            "last_message_age_seconds": (
                (now - datetime.fromisoformat(self.health_status["whatsapp"]["last_message_received"])).total_seconds()
                if self.health_status["whatsapp"].get("last_message_received")
                else None
            ),
            "processing_success_rate": (
                self.health_status["processing"]["successful_audios"] / self.health_status["processing"]["total_audios"]
                if self.health_status["processing"]["total_audios"] > 0
                else None
            ),
            "details": self.health_status
        }
        
        return status 