"""
Rotas do dashboard - páginas web e APIs
"""
from fastapi import APIRouter, Depends, HTTPException, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse, FileResponse
from sqlmodel import Session, select
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
import secrets
import logging

from ..database import get_db
from ..models import User, ClientLink, ClientResponse
from ..routes.auth import get_current_user

router = APIRouter(tags=["dashboard"])
logger = logging.getLogger(__name__)

# ==============================================
# PÁGINAS WEB (HTML)
# ==============================================

@router.get("/", response_class=HTMLResponse)
async def home_page():
    """Página inicial"""
    return FileResponse("app/templates/index.html")

@router.get("/dashboard", response_class=HTMLResponse)
async def dashboard_page():
    """Página principal do dashboard"""
    return FileResponse("app/templates/dashboard.html")

@router.get("/register", response_class=HTMLResponse)
async def register_page():
    """Página de cadastro/registro"""
    return FileResponse("app/templates/login.html")

@router.get("/logout")
async def logout_page(request: Request):
    """Logout do usuário"""
    return RedirectResponse("/auth/logout", status_code=302)

@router.get("/onboarding", response_class=HTMLResponse)
async def onboarding_page():
    """Página de onboarding/cadastro"""
    return FileResponse("app/templates/onboarding.html")

@router.get("/cancel", response_class=HTMLResponse)
async def cancel_page(request: Request):
    """Página de cancelamento de pagamento"""
    return templates.TemplateResponse("cancel.html", {
        "request": request,
        "title": "Pagamento Cancelado - Opina"
    })

# ==============================================
# PÁGINAS LEGAIS
# ==============================================

@router.get("/termos", response_class=HTMLResponse)
async def terms_page(request: Request):
    """Página de termos de uso"""
    return templates.TemplateResponse("termos.html", {
        "request": request,
        "title": "Termos de Uso - Opina"
    })

@router.get("/privacidade", response_class=HTMLResponse)
async def privacy_page(request: Request):
    """Página de política de privacidade"""
    return templates.TemplateResponse("privacidade.html", {
        "request": request,
        "title": "Política de Privacidade - Opina"
    })

# ==============================================
# APIS PARA DASHBOARD
# ==============================================

@router.get("/api/dashboard/stats")
async def get_dashboard_stats(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """Dashboard principal - estatísticas reais"""
    
    # Get all responses for user
    responses = db.exec(
        select(ClientResponse)
        .join(ClientLink)
        .where(ClientLink.user_id == current_user.id)
    ).all()
    
    total_count = len(responses)
    last_30_days = len([r for r in responses if (datetime.utcnow() - r.created_at).days <= 30])
    
    # Sentiment breakdown
    sentiment_count = {"positivo": 0, "negativo": 0, "neutro": 0}
    total_rating = 0
    rating_count = 0
    
    for response in responses:
        if response.sentiment in sentiment_count:
            sentiment_count[response.sentiment] += 1
        if response.rating:
            total_rating += response.rating
            rating_count += 1
    
    avg_rating = (total_rating / rating_count) if rating_count > 0 else 0.0
    
    # Get links count
    links = db.exec(
        select(ClientLink)
        .where(ClientLink.user_id == current_user.id)
    ).all()
    
    active_links = [l for l in links if l.is_active]
    
    return {
        "total_responses": total_count,
        "responses_last_30_days": last_30_days,
        "avg_rating": avg_rating,
        "sentiment_distribution": sentiment_count,
        "total_links": len(links),
        "active_links": len(active_links),
        "total_views": 0,  # TODO: Implement
        "conversion_rate": 0.0,  # TODO: Calculate
        "plan_type": current_user.plan_type.value,
        "trial_expires_at": current_user.trial_expires_at.isoformat() if current_user.trial_expires_at else None
    }

# ==============================================
# OUTRAS ROTAS COMENTADAS TEMPORARIAMENTE
# ==============================================

# @router.post("/dashboard/links/create")
# @router.post("/dashboard/links/{link_id}/toggle")
# @router.get("/api/dashboard/links")
# @router.get("/api/dashboard/trends") 
# @router.get("/api/dashboard/recent-feedbacks")
# ... outras rotas que dependem do banco ... 

@router.get("/dashboard/preview", response_class=HTMLResponse)
async def dashboard_preview(request: Request):
    """Prévia do dashboard com dados mock (sem autenticação)"""
    
    # Mock user for preview
    mock_user = {
        "id": "preview-123",
        "name": "Usuário Demo",
        "email": "demo@opina.live",
        "plan_type": "free",
        "avatar_url": None
    }
    
    # Mock realistic stats
    stats = {
        "total_responses": 47,
        "responses_last_30_days": 23,
        "avg_rating": 4.3,
        "sentiment_distribution": {"positivo": 32, "negativo": 8, "neutro": 7},
        "total_links": 3,
        "active_links": 2,
        "total_views": 156,
        "conversion_rate": 30.1,
        "plan_type": "free",
        "trial_expires_at": None
    }
    
    # Mock recent links
    recent_links = [
        {
            "id": 1,
            "title": "Feedback sobre atendimento",
            "description": "Avaliação do atendimento ao cliente",
            "link_token": "demo-link-1",
            "responses_count": 23,
            "views_count": 78,
            "is_active": True,
            "created_at": datetime.utcnow() - timedelta(days=2)
        },
        {
            "id": 2,
            "title": "Satisfação com produto",
            "description": "Opinião sobre nossos produtos",
            "link_token": "demo-link-2",
            "responses_count": 15,
            "views_count": 45,
            "is_active": True,
            "created_at": datetime.utcnow() - timedelta(days=5)
        },
        {
            "id": 3,
            "title": "Feedback pós-compra",
            "description": "Experiência após a compra",
            "link_token": "demo-link-3",
            "responses_count": 9,
            "views_count": 33,
            "is_active": False,
            "created_at": datetime.utcnow() - timedelta(days=7)
        }
    ]
    
    # Mock recent feedbacks
    recent_feedbacks = [
        {
            "id": 1,
            "client_name": "Maria Silva",
            "client_phone": "+5511987654321",
            "rating": 5,
            "sentiment": "positivo",
            "transcription": "Adorei o atendimento! Muito profissional e rápido.",
            "processed": True,
            "created_at": datetime.utcnow() - timedelta(hours=2)
        },
        {
            "id": 2,
            "client_name": "João Santos",
            "client_phone": "+5511876543210",
            "rating": 4,
            "sentiment": "positivo",
            "transcription": "Produto de qualidade, recomendo. Entrega foi rápida.",
            "processed": True,
            "created_at": datetime.utcnow() - timedelta(hours=6)
        },
        {
            "id": 3,
            "client_name": "Ana Costa",
            "client_phone": "+5511765432109",
            "rating": 3,
            "sentiment": "neutro",
            "transcription": "Achei o preço um pouco alto, mas o produto é bom.",
            "processed": True,
            "created_at": datetime.utcnow() - timedelta(hours=12)
        },
        {
            "id": 4,
            "client_name": "Carlos Oliveira",
            "client_phone": "+5511654321098",
            "rating": 2,
            "sentiment": "negativo",
            "transcription": "Demorou muito para chegar e não era exatamente o que esperava.",
            "processed": True,
            "created_at": datetime.utcnow() - timedelta(days=1)
        }
    ]
    
    return templates.TemplateResponse("dashboard.html", {
        "request": request,
        "user": mock_user,
        "stats": stats,
        "recent_links": recent_links,
        "recent_feedbacks": recent_feedbacks,
        "title": f"Dashboard Preview - Design System Opina"
    })

@router.get("/dashboard/preview/usage")
async def preview_usage_data():
    """Mock usage data for dashboard preview"""
    return {
        "status": "success",
        "usage_summary": {
            "usage": {
                "audios": {
                    "current": 3,
                    "limit": 5,
                    "percentage": 60
                }
            },
            "features": {
                "available": ["transcription", "sentiment_analysis", "basic_dashboard"]
            }
        },
        "recommendations": []
    } 