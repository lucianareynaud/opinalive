from datetime import datetime
from typing import Optional, Dict, Any
from sqlmodel import Session, select
from fastapi import HTTPException

from ..models import User, Subscription, PlanType, SubscriptionStatus
from ..services.stripe import StripeService
from ..database import get_db

class PaymentService:
    def __init__(self):
        self.stripe = StripeService()
    
    async def create_subscription(
        self,
        user: User,
        plan_type: PlanType,
        db: Session
    ) -> Dict[str, Any]:
        """
        Cria uma nova assinatura para o usuário
        """
        # Verifica se já tem assinatura ativa
        if user.stripe_customer_id:
            stmt = select(Subscription).where(
                Subscription.user_id == user.id,
                Subscription.status == SubscriptionStatus.ACTIVE
            )
            active_sub = db.exec(stmt).first()
            if active_sub:
                raise HTTPException(
                    status_code=400,
                    detail="Usuário já possui assinatura ativa"
                )
        
        # Cria customer no Stripe se não existir
        if not user.stripe_customer_id:
            customer_id = await self.stripe.create_customer(user)
            if not customer_id:
                raise HTTPException(
                    status_code=500,
                    detail="Erro ao criar customer no Stripe"
                )
            user.stripe_customer_id = customer_id
            db.add(user)
            db.commit()
        
        # Cria checkout session
        checkout = await self.stripe.create_checkout_session(
            customer_id=user.stripe_customer_id,
            plan_type=plan_type
        )
        
        if not checkout:
            raise HTTPException(
                status_code=500,
                detail="Erro ao criar sessão de checkout"
            )
        
        return {
            "checkout_url": checkout["url"],
            "session_id": checkout["id"]
        }
    
    async def handle_subscription_updated(
        self,
        subscription_id: str,
        status: SubscriptionStatus,
        current_period_end: datetime,
        db: Session
    ) -> None:
        """
        Atualiza status da assinatura quando recebe webhook do Stripe
        """
        stmt = select(Subscription).where(
            Subscription.stripe_subscription_id == subscription_id
        )
        subscription = db.exec(stmt).first()
        
        if not subscription:
            return
        
        subscription.status = status
        subscription.current_period_end = current_period_end
        subscription.updated_at = datetime.utcnow()
        
        if status == SubscriptionStatus.ACTIVE:
            # Atualiza plano do usuário
            subscription.user.plan_type = subscription.plan_type
        elif status == SubscriptionStatus.CANCELED:
            subscription.canceled_at = datetime.utcnow()
            # Volta para plano free quando período atual acabar
            if subscription.user.plan_type != PlanType.FREE:
                subscription.user.plan_type = PlanType.FREE
        
        db.add(subscription)
        db.add(subscription.user)
        db.commit()
    
    async def cancel_subscription(
        self,
        user: User,
        db: Session
    ) -> bool:
        """
        Cancela assinatura do usuário
        """
        stmt = select(Subscription).where(
            Subscription.user_id == user.id,
            Subscription.status == SubscriptionStatus.ACTIVE
        )
        subscription = db.exec(stmt).first()
        
        if not subscription:
            raise HTTPException(
                status_code=404,
                detail="Nenhuma assinatura ativa encontrada"
            )
        
        success = await self.stripe.cancel_subscription(
            subscription.stripe_subscription_id
        )
        
        if not success:
            raise HTTPException(
                status_code=500,
                detail="Erro ao cancelar assinatura no Stripe"
            )
        
        subscription.status = SubscriptionStatus.CANCELED
        subscription.canceled_at = datetime.utcnow()
        subscription.updated_at = datetime.utcnow()
        
        # Volta para plano free quando período atual acabar
        if user.plan_type != PlanType.FREE:
            user.plan_type = PlanType.FREE
        
        db.add(subscription)
        db.add(user)
        db.commit()
        
        return True
    
    async def get_subscription_status(
        self,
        user: User,
        db: Session
    ) -> Dict[str, Any]:
        """
        Retorna status da assinatura do usuário
        """
        stmt = select(Subscription).where(
            Subscription.user_id == user.id,
            Subscription.status == SubscriptionStatus.ACTIVE
        )
        subscription = db.exec(stmt).first()
        
        if not subscription:
            return {
                "has_subscription": False,
                "plan_type": user.plan_type.value,
                "trial_expires_at": user.trial_expires_at
            }
        
        return {
            "has_subscription": True,
            "plan_type": subscription.plan_type.value,
            "status": subscription.status.value,
            "current_period_end": subscription.current_period_end,
            "canceled_at": subscription.canceled_at
        } 