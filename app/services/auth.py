"""
Serviço de autenticação Google OAuth
"""
from typing import Optional, Dict, Any
import secrets
import httpx
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from datetime import datetime, timedelta
from fastapi import HTTPException, Request, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import jwt

from ..config import settings
from ..models import User, PlanType
from ..database import get_db
from .cnpj_control import cnpj_control_service
import logging

logger = logging.getLogger(__name__)

class AuthError(HTTPException):
    """Exceção personalizada para erros de autenticação"""
    pass

class GoogleOAuthService:
    """Serviço para autenticação Google OAuth"""
    
    def __init__(self):
        self.client_id = settings.GOOGLE_CLIENT_ID
        self.client_secret = settings.GOOGLE_CLIENT_SECRET
        self.redirect_uri = settings.GOOGLE_REDIRECT_URI
        self.auth_url = "https://accounts.google.com/o/oauth2/auth"
        self.token_url = "https://oauth2.googleapis.com/token"
        self.user_info_url = "https://www.googleapis.com/oauth2/v2/userinfo"
        
    def get_authorization_url(self, state: str = None) -> str:
        """Gera URL de autorização do Google"""
        if not state:
            state = secrets.token_urlsafe(32)
            
        params = {
            "client_id": self.client_id,
            "redirect_uri": self.redirect_uri,
            "scope": "openid email profile",
            "response_type": "code",
            "access_type": "offline",
            "state": state,
            "prompt": "consent"
        }
        
        query_string = "&".join([f"{k}={v}" for k, v in params.items()])
        return f"{self.auth_url}?{query_string}"
        
    async def exchange_code_for_token(self, code: str) -> Dict[str, Any]:
        """Troca código por token de acesso"""
        data = {
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "code": code,
            "grant_type": "authorization_code",
            "redirect_uri": self.redirect_uri
        }
        
        async with httpx.AsyncClient() as client:
            response = await client.post(self.token_url, data=data)
            
        if response.status_code != 200:
            raise AuthError(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Erro ao obter token: {response.text}"
            )
            
        return response.json()
        
    async def get_user_info(self, access_token: str) -> Dict[str, Any]:
        """Obtém informações do usuário do Google"""
        headers = {"Authorization": f"Bearer {access_token}"}
        
        async with httpx.AsyncClient() as client:
            response = await client.get(self.user_info_url, headers=headers)
            
        if response.status_code != 200:
            raise AuthError(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Erro ao obter dados do usuário: {response.text}"
            )
            
        return response.json()
        
    async def create_or_update_user(
        self, 
        google_user_info: Dict[str, Any], 
        db: AsyncSession,
        cnpj: str = None,
        company_name: str = None
    ) -> User:
        """Cria ou atualiza usuário baseado nos dados do Google"""
        
        google_id = google_user_info["id"]
        email = google_user_info["email"]
        name = google_user_info["name"]
        avatar_url = google_user_info.get("picture")
        
        # Busca usuário existente
        result = await db.execute(
            select(User).where(User.google_id == google_id)
        )
        user = result.scalar_one_or_none()
        
        if user:
            # Atualiza dados existentes
            user.name = name
            user.email = email
            user.avatar_url = avatar_url
            user.updated_at = datetime.utcnow()
        else:
            # Verifica se email já existe (conta duplicada)
            result = await db.execute(
                select(User).where(User.email == email)
            )
            existing_user = result.scalar_one_or_none()
            
            if existing_user:
                raise AuthError(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Email já cadastrado com outra conta Google"
                )
            
            # Cria novo usuário
            user = User(
                email=email,
                name=name,
                google_id=google_id,
                avatar_url=avatar_url,
                plan_type=PlanType.FREE,
                trial_expires_at=datetime.utcnow() + timedelta(days=7),
                is_active=True
            )
            db.add(user)
            
        # Se forneceu CNPJ, registra free tier
        if cnpj and company_name:
            await cnpj_control_service.register_free_tier_usage(
                user, cnpj, company_name, db
            )
        
        await db.commit()
        await db.refresh(user)
        return user
        
    def create_jwt_token(self, user: User) -> str:
        """Cria token JWT para o usuário"""
        payload = {
            "user_id": user.id,
            "email": user.email,
            "exp": datetime.utcnow() + timedelta(days=30)
        }
        
        return jwt.encode(payload, settings.SECRET_KEY, algorithm="HS256")
        
    def verify_jwt_token(self, token: str) -> Dict[str, Any]:
        """Verifica e decodifica token JWT"""
        try:
            payload = jwt.decode(
                token, 
                settings.SECRET_KEY, 
                algorithms=["HS256"]
            )
            return payload
        except jwt.ExpiredSignatureError:
            raise AuthError(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token expirado"
            )
        except jwt.InvalidTokenError:
            raise AuthError(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token inválido"
            )

class AuthService:
    """Serviço principal de autenticação"""
    
    def __init__(self):
        self.google_oauth = GoogleOAuthService()
        self.security = HTTPBearer(auto_error=False)
        
    async def get_current_user(
        self, 
        request: Request,
        db: AsyncSession
    ) -> Optional[User]:
        """Obtém usuário atual da sessão/token"""
        
        # Tenta obter token do cookie primeiro
        token = request.cookies.get("access_token")
        
        # Se não tem cookie, tenta Authorization header
        if not token:
            credentials: HTTPAuthorizationCredentials = await self.security(request)
            if credentials:
                token = credentials.credentials
                
        if not token:
            return None
            
        try:
            # Verifica token
            payload = self.google_oauth.verify_jwt_token(token)
            user_id = payload.get("user_id")
            
            # Busca usuário no banco
            result = await db.execute(
                select(User).where(User.id == user_id)
            )
            user = result.scalar_one_or_none()
            
            if not user or not user.is_active:
                return None
                
            return user
            
        except AuthError:
            return None
            
    async def require_auth(
        self, 
        request: Request, 
        db: AsyncSession
    ) -> User:
        """Requer autenticação - levanta exceção se não autenticado"""
        user = await self.get_current_user(request, db)
        
        if not user:
            raise AuthError(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Não autenticado"
            )
            
        return user
        
    async def require_plan(
        self, 
        user: User, 
        required_plans: list[str]
    ) -> bool:
        """Verifica se usuário tem plano necessário"""
        
        # Verifica se trial expirou
        if user.plan_type == "free" and user.trial_expires_at:
            if datetime.utcnow() > user.trial_expires_at:
                raise AuthError(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Trial expirado. Faça upgrade para continuar."
                )
        
        # Verifica plano
        if user.plan_type not in required_plans:
            raise AuthError(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Recurso disponível apenas para planos: {', '.join(required_plans)}"
            )
            
        return True

    async def require_cnpj_completion(self, user: User) -> bool:
        """Verifica se usuário completou dados do CNPJ"""
        if not user.cnpj or not user.company_name:
            raise AuthError(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="complete_cnpj_required"
            )
        
        return True

# Instância global
auth_service = AuthService() 