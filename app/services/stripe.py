import stripe
from typing import Optional, Dict, Any
import logging
from ..config import settings
from ..models import User, PlanType

logger = logging.getLogger(__name__)

# Configure Stripe with secret key
stripe.api_key = settings.STRIPE_SECRET_KEY

class StripeService:
    """
    Service for handling Stripe payments and subscriptions
    """
    
    @staticmethod
    async def create_customer(user: User) -> Optional[str]:
        """
        Create a Stripe customer for a user
        """
        try:
            customer = stripe.Customer.create(
                email=user.email,
                name=user.name,
                metadata={
                    "user_id": user.id,
                    "company_name": user.company_name or "",
                    "cnpj": user.cnpj or ""
                }
            )
            return customer.id
        except Exception as e:
            logger.error(f"Error creating Stripe customer: {e}")
            return None
    
    @staticmethod
    async def create_checkout_session(
        customer_id: str,
        plan_type: PlanType,
        trial_end: Optional[int] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Create a Stripe Checkout session for subscription
        """
        try:
            # Get price ID for plan
            price_id = StripeService.get_price_id_for_plan(plan_type)
            if not price_id:
                logger.error(f"No price ID found for plan: {plan_type}")
                return None
            
            # Create checkout session
            session = stripe.checkout.Session.create(
                customer=customer_id,
                payment_method_types=['card'],
                line_items=[{
                    'price': price_id,
                    'quantity': 1,
                }],
                mode='subscription',
                success_url=settings.STRIPE_SUCCESS_URL,
                cancel_url=settings.STRIPE_CANCEL_URL,
                locale='pt-BR',  # Português
                allow_promotion_codes=True,
                billing_address_collection='required',
                customer_update={
                    'address': 'auto',
                    'name': 'auto',
                },
                subscription_data={
                    'trial_end': trial_end,
                    'metadata': {
                        'plan_type': plan_type.value
                    }
                }
            )
            
            return {
                "id": session.id,
                "url": session.url
            }
        except Exception as e:
            logger.error(f"Error creating checkout session: {e}")
            return None
    
    @staticmethod
    async def cancel_subscription(subscription_id: str) -> bool:
        """
        Cancel a subscription
        """
        try:
            stripe.Subscription.delete(subscription_id)
            return True
        except Exception as e:
            logger.error(f"Error canceling subscription: {e}")
            return False
    
    @staticmethod
    async def get_subscription(subscription_id: str) -> Optional[Dict[str, Any]]:
        """
        Get subscription details
        """
        try:
            subscription = stripe.Subscription.retrieve(subscription_id)
            return {
                "id": subscription.id,
                "status": subscription.status,
                "current_period_end": subscription.current_period_end,
                "cancel_at": subscription.cancel_at,
                "canceled_at": subscription.canceled_at
            }
        except Exception as e:
            logger.error(f"Error getting subscription: {e}")
            return None
    
    @staticmethod
    async def handle_webhook(payload: bytes, signature: str) -> bool:
        """
        Handle Stripe webhook events
        """
        try:
            event = stripe.Webhook.construct_event(
                payload,
                signature,
                settings.STRIPE_WEBHOOK_SECRET
            )
            
            # Handle specific events
            if event.type == "checkout.session.completed":
                logger.info(f"Checkout completed: {event.data.object.id}")
                # Criar assinatura no banco
                subscription = event.data.object.subscription
                customer = event.data.object.customer
                plan_type = event.data.object.subscription_data.metadata.plan_type
                
            elif event.type == "customer.subscription.created":
                logger.info(f"Subscription created: {event.data.object.id}")
                
            elif event.type == "customer.subscription.updated":
                logger.info(f"Subscription updated: {event.data.object.id}")
                
            elif event.type == "customer.subscription.deleted":
                logger.info(f"Subscription canceled: {event.data.object.id}")
                
            elif event.type == "invoice.paid":
                logger.info(f"Invoice paid: {event.data.object.id}")
                
            elif event.type == "invoice.payment_failed":
                logger.info(f"Payment failed: {event.data.object.id}")
            
            return True
        except Exception as e:
            logger.error(f"Error handling webhook: {e}")
            return False
    
    @staticmethod
    def get_price_id_for_plan(plan_type: PlanType) -> Optional[str]:
        """
        Get Stripe price ID for a plan type
        """
        price_map = {
            PlanType.PRO: settings.STRIPE_PRICE_ID_PRO,
            PlanType.ENTERPRISE: settings.STRIPE_PRICE_ID_ENTERPRISE
        }
        return price_map.get(plan_type) 