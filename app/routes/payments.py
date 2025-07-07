from fastapi import APIRouter, Depends, HTTPException, Request, Header
from sqlmodel import Session
from typing import Optional, Dict, Any
from pydantic import BaseModel
import logging

from ..database import get_db
from ..services.payment import PaymentService
from ..models import User, PlanType
from ..config import settings
from ..dependencies import get_current_user

router = APIRouter()
logger = logging.getLogger(__name__)
payment_service = PaymentService()

class SubscriptionRequest(BaseModel):
    plan_type: PlanType

@router.post("/create-subscription")
async def create_subscription(
    request: SubscriptionRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Cria uma nova assinatura para o usuário
    """
    return await payment_service.create_subscription(
        user=user,
        plan_type=request.plan_type,
        db=db
    )

@router.post("/webhook")
async def stripe_webhook(
    request: Request,
    stripe_signature: str = Header(None),
    db: Session = Depends(get_db)
) -> Dict[str, str]:
    """
    Handle Stripe webhook events
    """
    if not stripe_signature:
        raise HTTPException(status_code=400, detail="No signature provided")
    
    # Get request body
    payload = await request.body()
    
    # Handle webhook
    success = await payment_service.stripe.handle_webhook(payload, stripe_signature)
    if not success:
        raise HTTPException(status_code=400, detail="Invalid webhook payload")
    
    return {"status": "success"}

@router.post("/cancel-subscription")
async def cancel_subscription(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> Dict[str, str]:
    """
    Cancela assinatura do usuário
    """
    success = await payment_service.cancel_subscription(user, db)
    if not success:
        raise HTTPException(status_code=500, detail="Failed to cancel subscription")
    
    return {"status": "subscription canceled"}

@router.get("/subscription-status")
async def get_subscription_status(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Retorna status da assinatura do usuário
    """
    return await payment_service.get_subscription_status(user, db)

@router.get("/config")
async def get_payment_config() -> Dict[str, Any]:
    """
    Retorna configurações públicas do Stripe
    """
    return {
        "publishableKey": settings.STRIPE_PUBLISHABLE_KEY,
        "prices": {
            "pro": settings.STRIPE_PRICE_ID_PRO,
            "enterprise": settings.STRIPE_PRICE_ID_ENTERPRISE
        }
    } 