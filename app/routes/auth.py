"""
Rotas de autenticação Google OAuth - SISTEMA REAL
"""
from fastapi import APIRouter, Request, Response, Depends, HTTPException, status
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlmodel import Session, select
from ..database import get_db
from ..models import User, PlanType
from ..config import settings
from ..services.auth import GoogleOAuthService, AuthService
import logging
import secrets

router = APIRouter(prefix="/auth", tags=["auth"])
templates = Jinja2Templates(directory="app/templates")
logger = logging.getLogger(__name__)

# Inicializar serviços
google_oauth = GoogleOAuthService()
auth_service = AuthService()

@router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    """Página de login"""
    return templates.TemplateResponse("login.html", {
        "request": request,
        "title": "Login - Opina"
    })

@router.get("/google")
async def google_login(request: Request):
    """Inicia processo de login com Google - OAUTH REAL"""
    try:
        # Gera estado de segurança
        state = secrets.token_urlsafe(32)
        
        # Armazena state na sessão (você pode usar Redis ou cookie)
        response = RedirectResponse(google_oauth.get_authorization_url(state), status_code=302)
        response.set_cookie("oauth_state", state, max_age=600, httponly=True)  # 10 minutos
        
        logger.info("Redirecionando para Google OAuth")
        return response
        
    except Exception as e:
        logger.error(f"Erro ao iniciar Google OAuth: {e}")
        return RedirectResponse("/login?error=oauth_error", status_code=302)

@router.get("/google/callback")
async def google_callback(
    request: Request, 
    code: str = None, 
    state: str = None, 
    error: str = None,
    db: Session = Depends(get_db)
):
    """Callback do Google OAuth - OAUTH REAL"""
    try:
        # Verifica se houve erro
        if error:
            logger.error(f"Erro do Google OAuth: {error}")
            return RedirectResponse("/login?error=oauth_error", status_code=302)
        
        # Verifica se o código foi fornecido
        if not code:
            logger.error("Código de autorização não fornecido")
            return RedirectResponse("/login?error=no_code", status_code=302)
        
        # Verifica state de segurança
        stored_state = request.cookies.get("oauth_state")
        if not stored_state or stored_state != state:
            logger.error("State de segurança inválido")
            return RedirectResponse("/login?error=invalid_state", status_code=302)
        
        # Troca código por token
        token_data = await google_oauth.exchange_code_for_token(code)
        access_token = token_data.get("access_token")
        
        if not access_token:
            logger.error("Token de acesso não recebido")
            return RedirectResponse("/login?error=no_token", status_code=302)
        
        # Obtém dados do usuário
        user_info = await google_oauth.get_user_info(access_token)
        
        # Cria ou atualiza usuário no banco
        user = await google_oauth.create_or_update_user(user_info, db)
        
        # Cria token JWT
        jwt_token = google_oauth.create_jwt_token(user)
        
        # Redireciona para dashboard com token
        response = RedirectResponse("/dashboard", status_code=302)
        response.set_cookie("access_token", jwt_token, max_age=30*24*60*60, httponly=True)  # 30 dias
        response.delete_cookie("oauth_state")  # Remove state temporário
        
        logger.info(f"Login bem-sucedido para usuário: {user.email}")
        return response
        
    except HTTPException as e:
        logger.error(f"Erro HTTP no callback: {e.detail}")
        return RedirectResponse(f"/login?error={e.detail}", status_code=302)
    except Exception as e:
        logger.error(f"Erro interno no callback: {e}")
        return RedirectResponse("/login?error=server_error", status_code=302)

@router.post("/logout")
@router.get("/logout")
async def logout(request: Request):
    """Logout do usuário"""
    response = RedirectResponse("/", status_code=302)
    response.delete_cookie("access_token")
    response.delete_cookie("oauth_state")
    logger.info("Usuário fez logout")
    return response

@router.get("/me")
async def get_current_user_info(request: Request, db: Session = Depends(get_db)):
    """Retorna informações do usuário atual - OAUTH REAL"""
    try:
        user = await auth_service.get_current_user(request, db)
        
        if not user:
            raise HTTPException(status_code=401, detail="Não autenticado")
        
        return {
            "id": user.id,
            "email": user.email,
            "name": user.name,
            "plan_type": user.plan_type,
            "is_active": user.is_active,
            "trial_expires_at": user.trial_expires_at.isoformat() if user.trial_expires_at else None
        }
        
    except Exception as e:
        logger.error(f"Erro ao obter usuário atual: {e}")
        raise HTTPException(status_code=500, detail="Erro interno")

# Dependencies para autenticação - OAUTH REAL
async def get_current_user(request: Request, db: Session = Depends(get_db)):
    """Dependency para obter usuário atual - OAUTH REAL"""
    user = await auth_service.get_current_user(request, db)
    
    if not user:
        raise HTTPException(
            status_code=401,
            detail="Não autenticado",
            headers={"WWW-Authenticate": "Bearer"}
        )
    
    return user

async def get_current_user_optional(request: Request, db: Session = Depends(get_db)):
    """Dependency para obter usuário atual (opcional) - OAUTH REAL"""
    return await auth_service.get_current_user(request, db)

# Middleware para verificar plano ativo
async def check_plan_access(
    current_user: User = Depends(get_current_user),
    required_plans: list[str] = ["free", "pro", "enterprise"]
):
    """Middleware para verificar se usuário tem acesso baseado no plano"""
    try:
        await auth_service.require_plan(current_user, required_plans)
        return current_user
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erro ao verificar plano: {e}")
        raise HTTPException(status_code=500, detail="Erro interno") 