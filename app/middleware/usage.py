"""
Middleware para enforçar guardrails de uso automaticamente
"""
from fastapi import Request, Response, HTTPException, status
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse
from ..services.usage import usage_service, UsageError
from ..services.auth import AuthService
from ..database import get_db
from ..models import FeatureType
import logging
import time
import json
from typing import Dict, Any
import structlog

# Configure structlog
structlog.configure(
    processors=[
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.JSONRenderer()
    ]
)

logger = structlog.get_logger()

class UsageMiddleware(BaseHTTPMiddleware):
    """Middleware para verificar limites de uso automaticamente"""
    
    def __init__(self, app, routes_config: dict = None):
        super().__init__(app)
        self.auth_service = AuthService()
        
        # Configuração de rotas que precisam de verificação
        self.routes_config = routes_config or {
            "/feedback/audio": {
                "check_audio_limit": True,
                "increment_audio_usage": True,
                "required_feature": FeatureType.BASIC_AI
            },
            "/feedback/advanced": {
                "check_audio_limit": True,
                "increment_audio_usage": True,
                "required_feature": FeatureType.ADVANCED_AI
            },
            "/api/": {
                "required_feature": FeatureType.API_ACCESS,
                "increment_api_usage": True
            },
            "/dashboard/reports": {
                "required_feature": FeatureType.DETAILED_REPORTS,
                "increment_reports_usage": True
            }
        }
    
    async def dispatch(self, request: Request, call_next):
        """Processa requisições aplicando guardrails quando necessário"""
        
        try:
            # Verifica se a rota precisa de verificação
            route_path = request.url.path
            route_config = self._get_route_config(route_path)
            
            if not route_config:
                # Rota não precisa de verificação
                return await call_next(request)
            
            # Só verifica em métodos que modificam estado
            if request.method not in ['POST', 'PUT', 'PATCH']:
                return await call_next(request)
            
            # Obtém usuário atual
            with next(get_db()) as db:
                user = await self.auth_service.get_current_user(request, db)
                
                if not user:
                    return JSONResponse(
                        status_code=status.HTTP_401_UNAUTHORIZED,
                        content={"detail": "Usuário não autenticado"}
                    )
                
                # Aplica verificações baseadas na configuração
                await self._apply_usage_checks(user, db, route_config)
                
                # Processa a requisição
                response = await call_next(request)
                
                # Incrementa contadores se a requisição foi bem-sucedida
                if response.status_code == 200:
                    await self._apply_usage_increments(user, db, route_config)
                
                return response
                
        except UsageError as e:
            logger.warning(f"Limite de uso atingido: {e.detail}")
            return JSONResponse(
                status_code=e.status_code,
                content={"detail": e.detail, "type": "usage_limit"}
            )
        except Exception as e:
            logger.error(f"Erro no middleware de uso: {e}")
            return await call_next(request)
    
    def _get_route_config(self, path: str) -> dict:
        """Retorna configuração da rota se ela precisa de verificação"""
        
        for route_pattern, config in self.routes_config.items():
            if path.startswith(route_pattern):
                return config
        
        return None
    
    async def _apply_usage_checks(self, user, db, config: dict):
        """Aplica verificações de uso baseadas na configuração"""
        
        # Verifica acesso à feature
        if "required_feature" in config:
            await usage_service.check_feature_access(user, config["required_feature"])
        
        # Verifica limite de áudios
        if config.get("check_audio_limit"):
            await usage_service.check_audio_limit(user, db)
    
    async def _apply_usage_increments(self, user, db, config: dict):
        """Aplica incrementos de uso após sucesso da operação"""
        
        # Incrementa uso de áudio
        if config.get("increment_audio_usage"):
            await usage_service.increment_audio_usage(user, db)
        
        # Incrementa uso de IA
        if config.get("increment_ai_usage"):
            ai_type = config.get("required_feature", FeatureType.BASIC_AI)
            await usage_service.increment_ai_usage(user, db, ai_type)
        
        # Incrementa uso de API
        if config.get("increment_api_usage"):
            await usage_service.increment_feature_usage(user, db, FeatureType.API_ACCESS)
        
        # Incrementa uso de relatórios
        if config.get("increment_reports_usage"):
            await usage_service.increment_feature_usage(user, db, FeatureType.DETAILED_REPORTS)


# Decorators para aplicar guardrails em rotas específicas
def require_audio_limit(func):
    """Decorator para verificar limite de áudios"""
    async def wrapper(*args, **kwargs):
        # Encontra user e db nos argumentos
        user = None
        db = None
        
        for arg in args:
            if hasattr(arg, 'plan_type'):  # É um User
                user = arg
            elif hasattr(arg, 'exec'):  # É uma Session
                db = arg
        
        # Busca nos kwargs também
        user = user or kwargs.get('user') or kwargs.get('current_user')
        db = db or kwargs.get('db')
        
        if user and db:
            await usage_service.check_audio_limit(user, db)
        
        return await func(*args, **kwargs)
    return wrapper

def require_feature(feature: FeatureType):
    """Decorator para verificar acesso a features"""
    def decorator(func):
        async def wrapper(*args, **kwargs):
            # Encontra user nos argumentos
            user = None
            
            for arg in args:
                if hasattr(arg, 'plan_type'):  # É um User
                    user = arg
                    break
            
            # Busca nos kwargs também
            user = user or kwargs.get('user') or kwargs.get('current_user')
            
            if user:
                await usage_service.check_feature_access(user, feature)
            
            return await func(*args, **kwargs)
        return wrapper
    return decorator

def track_audio_usage(func):
    """Decorator para rastrear uso de áudios"""
    async def wrapper(*args, **kwargs):
        # Executa a função primeiro
        result = await func(*args, **kwargs)
        
        # Encontra user e db nos argumentos
        user = None
        db = None
        
        for arg in args:
            if hasattr(arg, 'plan_type'):  # É um User
                user = arg
            elif hasattr(arg, 'exec'):  # É uma Session
                db = arg
        
        # Busca nos kwargs também
        user = user or kwargs.get('user') or kwargs.get('current_user')
        db = db or kwargs.get('db')
        
        # Incrementa uso após sucesso
        if user and db:
            await usage_service.increment_audio_usage(user, db)
        
        return result
    return wrapper

class StructuredLoggingMiddleware:
    async def __call__(self, request: Request, call_next):
        # Start timer
        start_time = time.time()
        
        # Create context
        context: Dict[str, Any] = {
            "method": request.method,
            "path": request.url.path,
            "client_ip": request.client.host if request.client else None,
        }
        
        # Add request ID if available
        if "X-Request-ID" in request.headers:
            context["request_id"] = request.headers["X-Request-ID"]
            
        try:
            # Log request
            logger.info("request_started", **context)
            
            # Process request
            response = await call_next(request)
            
            # Add response info to context
            context.update({
                "status_code": response.status_code,
                "duration_ms": int((time.time() - start_time) * 1000)
            })
            
            # Log response
            logger.info("request_completed", **context)
            
            return response
            
        except Exception as e:
            # Add error info to context
            context.update({
                "error": str(e),
                "error_type": type(e).__name__,
                "duration_ms": int((time.time() - start_time) * 1000)
            })
            
            # Log error
            logger.error("request_failed", **context)
            raise 