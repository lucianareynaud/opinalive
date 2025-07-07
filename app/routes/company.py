"""
Rotas para gerenciamento de dados da empresa e controle de CNPJ
"""
from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from sqlmodel import Session
from pydantic import BaseModel
from typing import Optional

from ..database import get_db
from ..models import User
from ..services.cnpj_control import cnpj_control_service, CNPJError
from .auth import get_current_user
import logging

router = APIRouter(prefix="/company", tags=["company"])
templates = Jinja2Templates(directory="app/templates")
logger = logging.getLogger(__name__)

class CNPJData(BaseModel):
    cnpj: str
    company_name: str

class CNPJCheckData(BaseModel):
    cnpj: str

@router.get("/setup", response_class=HTMLResponse)
async def company_setup_page(
    request: Request,
    current_user: User = Depends(get_current_user)
):
    """Página para configurar dados da empresa"""
    return templates.TemplateResponse("company_setup.html", {
        "request": request,
        "user": current_user,
        "title": "Configurar Empresa - Opina"
    })

@router.post("/check-cnpj")
async def check_cnpj_eligibility(
    data: CNPJCheckData,
    db: Session = Depends(get_db)
):
    """Verifica se CNPJ pode usar free tier"""
    try:
        result = await cnpj_control_service.check_free_tier_eligibility(data.cnpj, db)
        return result
    except CNPJError as e:
        return JSONResponse(
            status_code=e.status_code,
            content={"detail": e.detail, "can_use_free": False}
        )
    except Exception as e:
        logger.error(f"Erro ao verificar CNPJ: {e}")
        return JSONResponse(
            status_code=500,
            content={"detail": "Erro interno", "can_use_free": False}
        )

@router.post("/setup")
async def setup_company_data(
    data: CNPJData,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Configura dados da empresa para o usuário"""
    try:
        # Se usuário já tem CNPJ configurado, não permite alterar
        if current_user.cnpj and current_user.has_used_free_tier:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Dados da empresa já configurados e não podem ser alterados"
            )
        
        # Registra free tier para o CNPJ
        await cnpj_control_service.register_free_tier_usage(
            current_user, data.cnpj, data.company_name, db
        )
        
        return {
            "success": True,
            "message": "Dados da empresa configurados com sucesso",
            "cnpj": current_user.cnpj,
            "company_name": current_user.company_name
        }
        
    except CNPJError as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail)
    except Exception as e:
        logger.error(f"Erro ao configurar empresa: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erro interno ao configurar empresa"
        )

@router.get("/info")
async def get_company_info(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Retorna informações da empresa do usuário"""
    try:
        if not current_user.cnpj:
            return {
                "has_company": False,
                "needs_setup": True,
                "message": "Dados da empresa não configurados"
            }
        
        # Busca informações do CNPJ
        cnpj_info = await cnpj_control_service.get_cnpj_info(current_user.cnpj, db)
        
        return {
            "has_company": True,
            "needs_setup": False,
            "cnpj": current_user.cnpj,
            "company_name": current_user.company_name,
            "has_used_free_tier": current_user.has_used_free_tier,
            "free_tier_started_at": current_user.free_tier_started_at.isoformat() if current_user.free_tier_started_at else None,
            "cnpj_info": cnpj_info
        }
        
    except Exception as e:
        logger.error(f"Erro ao obter informações da empresa: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erro interno"
        )

@router.get("/cnpj/{cnpj}")
async def get_cnpj_details(
    cnpj: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)  # Admin check pode ser adicionado aqui
):
    """Retorna detalhes de um CNPJ específico"""
    try:
        cnpj_info = await cnpj_control_service.get_cnpj_info(cnpj, db)
        return cnpj_info
    except CNPJError as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail)
    except Exception as e:
        logger.error(f"Erro ao buscar CNPJ: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erro interno"
        )

@router.get("/validate-cnpj/{cnpj}")
async def validate_cnpj_format(cnpj: str):
    """Valida formato e matemática do CNPJ"""
    try:
        cnpj_formatted = cnpj_control_service.validate_cnpj(cnpj)
        return {
            "valid": True,
            "cnpj_formatted": cnpj_formatted,
            "message": "CNPJ válido (formato e dígitos verificadores)"
        }
    except CNPJError as e:
        return JSONResponse(
            status_code=400,
            content={
                "valid": False,
                "message": e.detail
            }
        )

@router.get("/lookup-cnpj/{cnpj}")
async def lookup_cnpj_data(cnpj: str):
    """Consulta dados da empresa via API externa"""
    try:
        # Primeiro valida o CNPJ matematicamente
        cnpj_formatted = cnpj_control_service.validate_cnpj(cnpj)
        
        # Depois consulta dados na Receita Federal
        external_data = await cnpj_control_service.validate_with_external_api(cnpj)
        
        return {
            "cnpj_formatted": cnpj_formatted,
            "math_validation": True,
            "external_data": external_data,
            "message": "CNPJ validado com sucesso"
        }
        
    except CNPJError as e:
        return JSONResponse(
            status_code=400,
            content={
                "valid": False,
                "math_validation": False,
                "message": e.detail
            }
        )
    except Exception as e:
        logger.error(f"Erro ao consultar dados do CNPJ: {e}")
        return JSONResponse(
            status_code=500,
            content={
                "valid": None,
                "message": "Erro interno na consulta"
            }
        )

# Middleware para verificar se usuário completou dados da empresa
async def require_company_setup(
    request: Request,
    current_user: User = Depends(get_current_user)
):
    """Middleware para garantir que usuário tenha dados da empresa configurados"""
    
    # Rotas que não precisam de verificação
    exempt_paths = [
        "/company/setup",
        "/company/check-cnpj",
        "/auth/logout",
        "/company/info"
    ]
    
    if request.url.path in exempt_paths:
        return current_user
    
    # Verifica se tem dados da empresa
    if not current_user.cnpj or not current_user.company_name:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="company_setup_required"
        )
    
    return current_user 