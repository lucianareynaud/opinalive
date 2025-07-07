"""
Serviço de Controle de CNPJ e Free Tier
Garante que apenas 1 empresa pode usar o free tier por CNPJ
"""
from datetime import datetime
from typing import Optional
from sqlmodel import Session, select
from fastapi import HTTPException, status
from ..models import User, PlanType
import re
import logging

logger = logging.getLogger(__name__)

class CNPJError(HTTPException):
    """Exceção para erros relacionados ao CNPJ"""
    pass

class CNPJControlService:
    """Serviço para controlar free tier por CNPJ"""
    
    def __init__(self):
        pass
    
    def validate_cnpj(self, cnpj: str) -> str:
        """Valida e normaliza CNPJ com verificação matemática real"""
        if not cnpj:
            raise CNPJError(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="CNPJ é obrigatório"
            )
        
        # Remove TODOS os caracteres que não são dígitos
        cnpj_clean = re.sub(r'[^\d]', '', cnpj)
        
        # Verifica se tem 14 dígitos
        if len(cnpj_clean) != 14:
            raise CNPJError(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"CNPJ deve ter 14 dígitos. Fornecido: {len(cnpj_clean)} dígitos"
            )
        
        # Verifica se não são todos iguais (CNPJs inválidos conhecidos)
        if cnpj_clean == cnpj_clean[0] * 14:
            raise CNPJError(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="CNPJ inválido - todos os dígitos iguais"
            )
        
        # Validação matemática dos dígitos verificadores
        if not self._validate_cnpj_checksum(cnpj_clean):
            raise CNPJError(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="CNPJ inválido - dígitos verificadores incorretos"
            )
        
        # Formata CNPJ no padrão oficial
        return f"{cnpj_clean[:2]}.{cnpj_clean[2:5]}.{cnpj_clean[5:8]}/{cnpj_clean[8:12]}-{cnpj_clean[12:]}"
    
    def _validate_cnpj_checksum(self, cnpj: str) -> bool:
        """Valida os dígitos verificadores do CNPJ usando algoritmo oficial"""
        try:
            # CNPJ deve ter exatamente 14 dígitos
            if len(cnpj) != 14:
                return False
            
            # Converte para lista de inteiros
            digits = [int(d) for d in cnpj]
            
            # Calcula primeiro dígito verificador
            sequence1 = [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
            sum1 = sum(digits[i] * sequence1[i] for i in range(12))
            remainder1 = sum1 % 11
            check_digit1 = 0 if remainder1 < 2 else 11 - remainder1
            
            # Verifica primeiro dígito
            if digits[12] != check_digit1:
                return False
            
            # Calcula segundo dígito verificador
            sequence2 = [6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
            sum2 = sum(digits[i] * sequence2[i] for i in range(13))
            remainder2 = sum2 % 11
            check_digit2 = 0 if remainder2 < 2 else 11 - remainder2
            
            # Verifica segundo dígito
            return digits[13] == check_digit2
            
        except (ValueError, IndexError):
            return False
    
    async def validate_with_external_api(self, cnpj: str) -> dict:
        """
        Valida CNPJ com API externa (opcional)
        Pode ser usado para obter dados da empresa
        """
        try:
            # Remove formatação
            cnpj_clean = re.sub(r'[^\d]', '', cnpj)
            
            # Aqui você pode integrar com APIs como:
            # - Receita Federal (oficial, mas limitada)
            # - Brasil API (gratuita)
            # - Consultas pagas (mais dados)
            
            # Exemplo com Brasil API (gratuita)
            import httpx
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"https://brasilapi.com.br/api/cnpj/v1/{cnpj_clean}",
                    timeout=5.0
                )
                
                if response.status_code == 200:
                    data = response.json()
                    return {
                        "valid": True,
                        "company_name": data.get("razao_social", ""),
                        "fantasy_name": data.get("nome_fantasia", ""),
                        "activity": data.get("cnae_fiscal_descricao", ""),
                        "city": data.get("municipio", ""),
                        "state": data.get("uf", ""),
                        "status": data.get("situacao_cadastral", ""),
                        "api_source": "brasilapi"
                    }
                else:
                    return {
                        "valid": False,
                        "error": "CNPJ não encontrado na base da Receita Federal",
                        "api_source": "brasilapi"
                    }
                    
        except Exception as e:
            logger.warning(f"Erro ao consultar API externa para CNPJ {cnpj}: {e}")
            return {
                "valid": None,
                "error": "Erro na consulta externa - usando apenas validação matemática",
                "api_source": "error"
            }
    
    async def check_free_tier_eligibility(self, cnpj: str, db: Session) -> dict:
        """Verifica se o CNPJ pode usar free tier - RESTRIÇÃO VITALÍCIA"""
        
        # Normaliza CNPJ
        cnpj_formatted = self.validate_cnpj(cnpj)
        cnpj_clean = re.sub(r'[^\d]', '', cnpj_formatted)
        
        # Busca usuários com este CNPJ
        stmt = select(User).where(
            User.cnpj.like(f"%{cnpj_clean}%")
        )
        existing_users = db.exec(stmt).all()
        
        # Verifica se já tem alguém que USOU free tier (VITALÍCIO)
        free_tier_users = [
            user for user in existing_users 
            if user.has_used_free_tier  # VITALÍCIO - uma vez True, sempre True
        ]
        
        if free_tier_users:
            # CNPJ já utilizou free tier - BLOQUEADO PARA SEMPRE
            active_user = free_tier_users[0]
            return {
                "can_use_free": False,
                "reason": "cnpj_permanently_blocked",
                "existing_user": {
                    "email": active_user.email,
                    "name": active_user.name,
                    "company_name": active_user.company_name,
                    "plan_type": active_user.plan_type.value,
                    "free_tier_started_at": active_user.free_tier_started_at.isoformat() if active_user.free_tier_started_at else None
                },
                "message": f"CNPJ {cnpj_formatted} já utilizou o plano gratuito. Esta restrição é VITALÍCIA - cada empresa só pode usar o free tier UMA ÚNICA VEZ. Para adicionar mais usuários, é necessário upgrade para plano pago."
            }
        
        # Pode usar free tier (PRIMEIRA E ÚNICA VEZ)
        return {
            "can_use_free": True,
            "reason": "eligible_first_time",
            "cnpj_formatted": cnpj_formatted,
            "message": f"CNPJ {cnpj_formatted} elegível para plano gratuito (primeira e única vez)"
        }
    
    async def register_free_tier_usage(self, user: User, cnpj: str, company_name: str, db: Session) -> None:
        """Registra o uso do free tier para o CNPJ - MARCA VITALÍCIA"""
        
        # Valida CNPJ
        cnpj_formatted = self.validate_cnpj(cnpj)
        
        # Verifica elegibilidade (deve ser primeira vez)
        eligibility = await self.check_free_tier_eligibility(cnpj, db)
        
        if not eligibility["can_use_free"]:
            raise CNPJError(
                status_code=status.HTTP_409_CONFLICT,
                detail=eligibility["message"]
            )
        
        # MARCA VITALÍCIA - uma vez True, NUNCA mais pode usar free tier
        user.cnpj = cnpj_formatted
        user.company_name = company_name
        user.has_used_free_tier = True  # VITALÍCIO - nunca muda
        user.free_tier_started_at = datetime.utcnow()  # Data histórica
        user.plan_type = PlanType.FREE
        user.updated_at = datetime.utcnow()
        
        db.add(user)
        db.commit()
        db.refresh(user)
        
        logger.info(f"FREE TIER VITALÍCIO registrado para CNPJ {cnpj_formatted} - usuário {user.email}")
        logger.warning(f"CNPJ {cnpj_formatted} PERMANENTEMENTE BLOQUEADO para novos free tiers")
    
    async def get_cnpj_info(self, cnpj: str, db: Session) -> dict:
        """Retorna informações sobre o CNPJ"""
        
        # Normaliza CNPJ
        cnpj_formatted = self.validate_cnpj(cnpj)
        cnpj_clean = re.sub(r'[^\d]', '', cnpj_formatted)
        
        # Busca usuários com este CNPJ
        stmt = select(User).where(
            User.cnpj.like(f"%{cnpj_clean}%")
        )
        users = db.exec(stmt).all()
        
        if not users:
            return {
                "cnpj": cnpj_formatted,
                "has_users": False,
                "can_use_free": True,
                "users": []
            }
        
        # Organiza informações
        users_info = []
        has_free_tier = False
        
        for user in users:
            users_info.append({
                "email": user.email,
                "name": user.name,
                "company_name": user.company_name,
                "plan_type": user.plan_type.value,
                "has_used_free_tier": user.has_used_free_tier,
                "created_at": user.created_at.isoformat(),
                "is_active": user.is_active
            })
            
            if user.has_used_free_tier or user.plan_type == PlanType.FREE:
                has_free_tier = True
        
        return {
            "cnpj": cnpj_formatted,
            "has_users": True,
            "can_use_free": not has_free_tier,
            "users": users_info,
            "company_name": users[0].company_name if users else None
        }
    
    async def allow_additional_users(self, cnpj: str, db: Session) -> dict:
        """
        Verifica se pode adicionar mais usuários no mesmo CNPJ
        REGRA: Se CNPJ já usou free tier, só aceita novos usuários com plano PAGO
        """
        
        # Normaliza CNPJ
        cnpj_formatted = self.validate_cnpj(cnpj)
        cnpj_clean = re.sub(r'[^\d]', '', cnpj_formatted)
        
        # Busca usuários com este CNPJ
        stmt = select(User).where(
            User.cnpj.like(f"%{cnpj_clean}%")
        )
        users = db.exec(stmt).all()
        
        # Se não tem usuários, pode adicionar (será o primeiro)
        if not users:
            return {
                "can_add": True,
                "reason": "first_user",
                "message": "Primeiro usuário do CNPJ - pode usar free tier"
            }
        
        # Verifica se alguém já usou free tier
        has_used_free = any(user.has_used_free_tier for user in users)
        
        if has_used_free:
            # CNPJ já usou free tier - só aceita novos usuários com plano PAGO
            paid_users = [user for user in users if user.plan_type in [PlanType.PRO, PlanType.ENTERPRISE]]
            
            if not paid_users:
                return {
                    "can_add": False,
                    "reason": "needs_paid_plan",
                    "message": f"CNPJ {cnpj_formatted} já utilizou o free tier. Para adicionar novos usuários, pelo menos um usuário deve ter plano Pro ou Enterprise."
                }
            
            return {
                "can_add": True,
                "reason": "has_paid_users",
                "message": f"Pode adicionar usuário - CNPJ já tem planos pagos ativos",
                "paid_users_count": len(paid_users)
            }
        
        # CNPJ ainda não usou free tier
        return {
            "can_add": True,
            "reason": "free_tier_available", 
            "message": "CNPJ ainda pode usar free tier pela primeira vez"
        }


# Instância global do serviço
cnpj_control_service = CNPJControlService() 