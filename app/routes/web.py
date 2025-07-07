from fastapi import APIRouter, Depends
from typing import Dict, Any
from fastapi.responses import HTMLResponse, RedirectResponse, FileResponse
from sqlalchemy.orm import Session
from sqlalchemy import select

from ..dependencies import get_current_user, get_db
from ..models import User, Subscription, SubscriptionStatus
from ..config import settings

router = APIRouter()

@router.get("/api/user/me")
async def get_user_info(
    user: User = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    Retorna informações do usuário logado
    """
    return {
        "id": user.id,
        "email": user.email,
        "name": user.name,
        "avatar_url": user.avatar_url,
        "company_name": user.company_name,
        "plan_type": user.plan_type.value,
        "trial_expires_at": user.trial_expires_at,
        "is_active": user.is_active,
        "brand_color": user.brand_color,
        "logo_url": user.logo_url,
        "welcome_message": user.welcome_message,
        "max_responses_per_month": user.max_responses_per_month,
        "responses_this_month": user.responses_this_month,
        "current_month_audios": user.current_month_audios
    }

@router.get("/api/config/public")
async def get_public_config() -> Dict[str, Any]:
    """
    Retorna configurações públicas da aplicação
    """
    return {
        "stripe": {
            "publishableKey": settings.STRIPE_PUBLISHABLE_KEY,
            "prices": {
                "pro": settings.STRIPE_PRICE_ID_PRO,
                "enterprise": settings.STRIPE_PRICE_ID_ENTERPRISE
            }
        },
        "plans": {
            "free": {
                "name": "Free",
                "price": 0,
                "features": [
                    "5 áudios por mês",
                    "Dashboard básico",
                    "Análise de sentimento"
                ]
            },
            "pro": {
                "name": "Pro",
                "price": 29,
                "features": [
                    "15 áudios por mês",
                    "Dashboard completo",
                    "Análise avançada",
                    "Relatórios detalhados",
                    "Suporte em 48h"
                ]
            },
            "enterprise": {
                "name": "Enterprise",
                "price": "Sob consulta",
                "features": [
                    "Áudios ilimitados",
                    "Dashboard personalizado",
                    "API dedicada",
                    "Integrações customizadas",
                    "Suporte em 24h"
                ]
            }
        }
    }

@router.get("/cancelar-assinatura", response_class=HTMLResponse)
async def cancel_subscription_page():
    """Página de cancelamento de assinatura"""
    return FileResponse("app/templates/cancel_subscription.html") 