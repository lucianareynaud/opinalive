"""
Serviço de Gerenciamento de Uso e Guardrails
Sistema para enforçar limites por plano e rastrear uso
"""
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
from sqlmodel import Session, select, func
from fastapi import HTTPException, status
from ..models import User, UsageTracking, PlanType, FeatureType, PLAN_LIMITS
import logging

logger = logging.getLogger(__name__)

class UsageError(HTTPException):
    """Exceção personalizada para erros de uso"""
    pass

class UsageService:
    """Serviço para gerenciar uso e guardrails"""
    
    def __init__(self):
        self.plan_limits = PLAN_LIMITS
    
    # ==============================================
    # VERIFICAÇÃO DE LIMITES
    # ==============================================
    
    async def check_audio_limit(self, user: User, db: Session) -> bool:
        """Verifica se o usuário pode processar mais áudios este mês"""
        
        # Atualiza contador se necessário
        await self._ensure_monthly_reset(user, db)
        
        # Verifica limite do plano
        plan_limit = self.plan_limits[user.plan_type]["monthly_audios"]
        
        # Enterprise tem limite ilimitado
        if plan_limit == -1:
            return True
            
        # Verifica se ainda está dentro do limite
        if user.current_month_audios >= plan_limit:
            raise UsageError(
                status_code=status.HTTP_402_PAYMENT_REQUIRED,
                detail=f"Limite de {plan_limit} áudios por mês atingido. Link temporariamente suspenso até próximo ciclo ou upgrade."
            )
        
        return True
    
    async def check_feature_access(self, user: User, feature: FeatureType) -> bool:
        """Verifica se o usuário tem acesso a uma feature específica"""
        
        plan_features = self.plan_limits[user.plan_type]["features"]
        
        if feature not in plan_features:
            raise UsageError(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Feature {feature.value} não disponível no plano {user.plan_type.value}"
            )
        
        return True
    
    # ==============================================
    # TRACKING DE USO
    # ==============================================
    
    async def increment_audio_usage(self, user: User, db: Session) -> None:
        """Incrementa o uso de áudios do usuário"""
        
        # Verifica limite primeiro
        await self.check_audio_limit(user, db)
        
        # Incrementa contador
        user.current_month_audios += 1
        user.updated_at = datetime.utcnow()
        
        # Atualiza tracking detalhado
        await self._update_usage_tracking(user, db, "audios_processed", 1)
        
        db.add(user)
        db.commit()
        db.refresh(user)
        
        logger.info(f"Uso de áudio incrementado para usuário {user.email}: {user.current_month_audios}/{self.plan_limits[user.plan_type]['monthly_audios']}")
    
    async def increment_ai_usage(self, user: User, db: Session, ai_type: FeatureType) -> None:
        """Incrementa o uso de IA do usuário"""
        
        # Verifica acesso à feature
        await self.check_feature_access(user, ai_type)
        
        # Mapeia tipo de IA para campo de tracking
        ai_mapping = {
            FeatureType.BASIC_AI: "basic_ai_calls",
            FeatureType.ADVANCED_AI: "advanced_ai_calls",
            FeatureType.CUSTOM_AI: "custom_ai_calls"
        }
        
        field_name = ai_mapping.get(ai_type)
        if field_name:
            await self._update_usage_tracking(user, db, field_name, 1)
        
        logger.info(f"Uso de IA {ai_type.value} incrementado para usuário {user.email}")
    
    async def increment_feature_usage(self, user: User, db: Session, feature: FeatureType) -> None:
        """Incrementa o uso de uma feature específica"""
        
        # Verifica acesso à feature
        await self.check_feature_access(user, feature)
        
        # Mapeia features para campos de tracking
        feature_mapping = {
            FeatureType.DETAILED_REPORTS: "reports_generated",
            FeatureType.API_ACCESS: "api_calls"
        }
        
        field_name = feature_mapping.get(feature)
        if field_name:
            await self._update_usage_tracking(user, db, field_name, 1)
        
        logger.info(f"Uso de feature {feature.value} incrementado para usuário {user.email}")
    
    # ==============================================
    # RELATÓRIOS DE USO
    # ==============================================
    
    async def get_usage_summary(self, user: User, db: Session) -> Dict[str, Any]:
        """Retorna resumo do uso atual do usuário"""
        
        # Garante reset mensal
        await self._ensure_monthly_reset(user, db)
        
        # Dados do plano
        plan_limits = self.plan_limits[user.plan_type]
        
        # Tracking detalhado do mês atual
        current_month = datetime.utcnow()
        stmt = select(UsageTracking).where(
            UsageTracking.user_id == user.id,
            UsageTracking.year == current_month.year,
            UsageTracking.month == current_month.month
        )
        tracking = db.exec(stmt).first()
        
        return {
            "plan_type": user.plan_type.value,
            "usage": {
                "audios": {
                    "current": user.current_month_audios,
                    "limit": plan_limits["monthly_audios"],
                    "percentage": (user.current_month_audios / plan_limits["monthly_audios"] * 100) if plan_limits["monthly_audios"] > 0 else 0
                }
            },
            "features": {
                "available": [f.value for f in plan_limits["features"]],
                "support_hours": plan_limits["support_hours"]
            },
            "tracking": {
                "basic_ai_calls": tracking.basic_ai_calls if tracking else 0,
                "advanced_ai_calls": tracking.advanced_ai_calls if tracking else 0,
                "custom_ai_calls": tracking.custom_ai_calls if tracking else 0,
                "reports_generated": tracking.reports_generated if tracking else 0,
                "api_calls": tracking.api_calls if tracking else 0
            } if tracking else {},
            "month_start": user.current_month_start.isoformat(),
            "next_reset": (user.current_month_start + timedelta(days=32)).replace(day=1).isoformat()
        }
    
    async def get_upgrade_recommendations(self, user: User, db: Session) -> List[Dict[str, Any]]:
        """Retorna recomendações de upgrade baseadas no uso"""
        
        usage_summary = await self.get_usage_summary(user, db)
        recommendations = []
        
        # Se está no limite de áudios (80% ou mais)
        if usage_summary["usage"]["audios"]["percentage"] >= 80:
            if user.plan_type == PlanType.FREE:
                recommendations.append({
                    "type": "audio_limit",
                    "message": "Você já usou 80% dos seus áudios mensais. Considere upgrade para Pro (15 áudios/mês)",
                    "upgrade_to": "pro"
                })
            elif user.plan_type == PlanType.PRO:
                recommendations.append({
                    "type": "audio_limit", 
                    "message": "Você já usou 80% dos seus áudios mensais. Considere upgrade para Enterprise (ilimitado)",
                    "upgrade_to": "enterprise"
                })
        
        # Se atingiu o limite (100%)
        if usage_summary["usage"]["audios"]["percentage"] >= 100:
            recommendations.append({
                "type": "limit_reached",
                "message": "Limite de áudios atingido! Seu link está temporariamente suspenso.",
                "upgrade_to": "upgrade"
            })
        
        return recommendations
    
    # ==============================================
    # UTILITÁRIOS INTERNOS
    # ==============================================
    
    async def _ensure_monthly_reset(self, user: User, db: Session) -> None:
        """
        Garante que APENAS OS CONTADORES DE USO sejam resetados mensalmente
        IMPORTANTE: A elegibilidade para free tier (has_used_free_tier) é VITALÍCIA
        """
        
        current_date = datetime.utcnow()
        current_month_start = current_date.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        
        # Se mudou de mês, reseta APENAS os contadores de uso
        if user.current_month_start < current_month_start:
            # RESETA MENSALMENTE:
            user.current_month_audios = 0  # Contador de áudios do mês
            user.current_month_start = current_month_start
            user.last_reset_date = current_date
            user.updated_at = current_date
            
            # NUNCA RESETA (VITALÍCIO):
            # - user.has_used_free_tier (permanece True para sempre)
            # - user.free_tier_started_at (data histórica)
            # - user.cnpj (dados da empresa)
            
            db.add(user)
            db.commit()
            db.refresh(user)
            
            logger.info(f"Contadores mensais resetados para usuário {user.email}")
            logger.info(f"CNPJ {user.cnpj} mantém restrição VITALÍCIA de free tier")
    
    async def _update_usage_tracking(self, user: User, db: Session, field_name: str, increment: int = 1) -> None:
        """Atualiza o tracking detalhado de uso"""
        
        current_date = datetime.utcnow()
        
        # Busca ou cria entrada de tracking do mês atual
        stmt = select(UsageTracking).where(
            UsageTracking.user_id == user.id,
            UsageTracking.year == current_date.year,
            UsageTracking.month == current_date.month
        )
        tracking = db.exec(stmt).first()
        
        if not tracking:
            tracking = UsageTracking(
                user_id=user.id,
                year=current_date.year,
                month=current_date.month
            )
            db.add(tracking)
        
        # Incrementa o campo específico
        current_value = getattr(tracking, field_name, 0)
        setattr(tracking, field_name, current_value + increment)
        tracking.updated_at = current_date
        
        db.commit()
        db.refresh(tracking)
    
    # ==============================================
    # DECORATORS / MIDDLEWARES
    # ==============================================
    
    def require_feature(self, feature: FeatureType):
        """Decorator para verificar acesso a features"""
        def decorator(func):
            async def wrapper(user: User, *args, **kwargs):
                await self.check_feature_access(user, feature)
                return await func(user, *args, **kwargs)
            return wrapper
        return decorator
    
    def require_audio_limit(self, func):
        """Decorator para verificar limite de áudios"""
        async def wrapper(user: User, db: Session, *args, **kwargs):
            await self.check_audio_limit(user, db)
            return await func(user, db, *args, **kwargs)
        return wrapper


# Instância global do serviço
usage_service = UsageService() 