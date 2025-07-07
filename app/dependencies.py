"""
Dependências compartilhadas da aplicação
"""
from fastapi import Depends, HTTPException, Request, status
from sqlmodel import Session
from typing import Optional
import logging

from .database import get_db
from .services.auth import AuthService
from .models import User

logger = logging.getLogger(__name__)

# Initialize auth service
auth_service = AuthService()

async def get_current_user(request: Request, db: Session = Depends(get_db)) -> User:
    """
    Dependency para obter usuário atual - OAuth real
    """
    user = await auth_service.get_current_user(request, db)
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Não autenticado",
            headers={"WWW-Authenticate": "Bearer"}
        )
    
    return user

async def get_current_user_optional(request: Request, db: Session = Depends(get_db)) -> Optional[User]:
    """
    Dependency para obter usuário atual (opcional) - OAuth real
    """
    return await auth_service.get_current_user(request, db) 