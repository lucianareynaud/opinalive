from sqlmodel import Session, select, func
from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta
import logging
from collections import Counter
import json

from ..models import User, ClientLink, ClientResponse, PlanType
from ..config import settings
from ..services.transcription import TranscriptionService
from ..services.openai import OpenAIService

logger = logging.getLogger(__name__)

class BusinessService:
    """
    Service for business logic operations
    """
    
    def __init__(self, db: Session, openai: OpenAIService):
        self.db = db
        self.transcription = TranscriptionService()
        self.openai = openai
    
    def get_plan_limits(self, plan: PlanType) -> Dict[str, int]:
        """
        Get audio limits for a plan
        """
        limits = {
            PlanType.FREE: settings.FREE_PLAN_AUDIO_LIMIT,
            PlanType.PRO: settings.PRO_PLAN_AUDIO_LIMIT,
            PlanType.ENTERPRISE: settings.ENTERPRISE_PLAN_AUDIO_LIMIT
        }
        return {
            "audio_limit": limits.get(plan, 10),
            "plan": plan.value
        }
    
    def get_user_usage(self, user_id: int) -> Dict[str, Any]:
        """
        Get current usage statistics for a user
        """
        # Get total response count
        total_responses = self.db.exec(
            select(func.count(ClientResponse.id))
            .join(ClientLink)
            .where(ClientLink.user_id == user_id)
        ).first()
        
        # Get this month's response count
        start_of_month = datetime.now().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        monthly_responses = self.db.exec(
            select(func.count(ClientResponse.id))
            .join(ClientLink)
            .where(
                ClientLink.user_id == user_id,
                ClientResponse.created_at >= start_of_month
            )
        ).first()
        
        # Get processed response count
        processed_responses = self.db.exec(
            select(func.count(ClientResponse.id))
            .join(ClientLink)
            .where(
                ClientLink.user_id == user_id,
                ClientResponse.processed == True
            )
        ).first()
        
        # Get active links count
        active_links = self.db.exec(
            select(func.count(ClientLink.id))
            .where(
                ClientLink.user_id == user_id,
                ClientLink.is_active == True
            )
        ).first()
        
        return {
            "total_responses": total_responses or 0,
            "monthly_responses": monthly_responses or 0,
            "processed_responses": processed_responses or 0,
            "pending_responses": (total_responses or 0) - (processed_responses or 0),
            "active_links": active_links or 0
        }
    
    def can_process_more_audio(self, user_id: int) -> Dict[str, Any]:
        """
        Check if user can process more audio based on their plan limits
        """
        # Get user
        user = self.db.exec(
            select(User).where(User.id == user_id)
        ).first()
        
        if not user:
            return {
                "can_process": False,
                "reason": "User not found",
                "current_usage": 0,
                "limit": 0
            }
        
        # Check if trial expired
        if user.plan_type == PlanType.FREE and user.trial_expires_at:
            if datetime.utcnow() > user.trial_expires_at:
                return {
                    "can_process": False,
                    "reason": "Trial expired",
                    "current_usage": 0,
                    "limit": 0,
                    "trial_expired": True
                }
        
        # Get plan limits
        plan_info = self.get_plan_limits(user.plan_type)
        audio_limit = plan_info["audio_limit"]
        
        # Get current usage
        usage = self.get_user_usage(user_id)
        current_usage = usage["monthly_responses"]
        
        can_process = current_usage < audio_limit
        
        return {
            "can_process": can_process,
            "reason": "Limit exceeded" if not can_process else "Within limits",
            "current_usage": current_usage,
            "limit": audio_limit,
            "plan": user.plan_type.value,
            "remaining": max(0, audio_limit - current_usage),
            "trial_expired": False
        }
    
    def find_user_by_link(self, link_id: str) -> Optional[User]:
        """
        Find user by link ID - critical for webhook processing
        """
        # Get link
        link = self.db.exec(
            select(ClientLink).where(ClientLink.link_id == link_id)
        ).first()
        
        if not link:
            return None
        
        # Get user
        user = self.db.exec(
            select(User).where(User.id == link.user_id)
        ).first()
        
        return user
    
    async def find_user_by_phone(self, phone: str, db: Session) -> Optional[User]:
        """Find a user by their phone number"""
        stmt = select(User).where(User.phone == phone)
        result = db.exec(stmt).first()
        return result

    def create_response_entry(self, link_id: int, client_phone: str, audio_url: str) -> Optional[ClientResponse]:
        """Create a new response entry"""
        try:
            response = ClientResponse(
                link_id=link_id,
                client_phone=client_phone,
                audio_url=audio_url
            )
            self.db.add(response)
            self.db.commit()
            self.db.refresh(response)
            return response
        except Exception as e:
            logger.error(f"Error creating response: {e}")
            return None

    async def process_response(self, response_id: int, db: Session, audio_bytes: bytes):
        """Process an audio response"""
        try:
            # Get response from DB
            response = db.get(ClientResponse, response_id)
            if not response:
                logger.error(f"Response {response_id} not found")
                return
            
            # Get link to get context
            link = db.get(ClientLink, response.link_id)
            if not link:
                logger.error(f"Link {response.link_id} not found")
                return
            
            # Transcribe audio
            try:
                transcription = await self.transcription.transcribe_audio(audio_bytes)
                response.transcription = transcription
                response.status = "transcribed"
                db.commit()
            except Exception as e:
                logger.error(f"Error transcribing audio: {e}")
                response.status = "failed"
                response.error = str(e)
                db.commit()
                return
            
            # Analyze with OpenAI
            try:
                analysis = await self.openai.analyze_feedback(
                    transcription,
                    link.context or "Feedback geral sobre o serviço/produto"
                )
                response.analysis = analysis
                response.status = "completed"
                db.commit()
            except Exception as e:
                logger.error(f"Error analyzing transcription: {e}")
                response.status = "failed"
                response.error = str(e)
                db.commit()
                return
            
            logger.info(f"Successfully processed response {response_id}")
            
        except Exception as e:
            logger.error(f"Error processing response {response_id}: {e}")
            try:
                response = db.get(ClientResponse, response_id)
                if response:
                    response.status = "failed"
                    response.error = str(e)
                    db.commit()
            except:
                pass
    
    def update_response_analysis(
        self,
        response_id: int,
        transcription: str,
        sentiment: str,
        rating: int = None
    ) -> bool:
        """
        Update response with analysis results
        """
        response = self.db.exec(
            select(ClientResponse).where(ClientResponse.id == response_id)
        ).first()
        
        if not response:
            logger.error(f"Response {response_id} not found")
            return False
        
        response.transcription = transcription
        response.sentiment = sentiment
        if rating:
            response.rating = rating
        response.processed = True
        response.updated_at = datetime.utcnow()
        
        self.db.add(response)
        self.db.commit()
        
        logger.info(f"Updated response {response_id} with analysis")
        return True
    
    def get_user_feedback_stats(self, user_id: int) -> Dict[str, Any]:
        """
        Get comprehensive feedback statistics for a user
        """
        # Get usage data
        usage = self.get_user_usage(user_id)
        
        # Get user info
        user = self.db.exec(
            select(User).where(User.id == user_id)
        ).first()
        
        if not user:
            return {}
        
        # Get plan info
        plan_info = self.get_plan_limits(user.plan_type)
        
        # Get sentiment breakdown
        sentiment_stats = {}
        for sentiment in ["positive", "negative", "neutral"]:
            count = self.db.exec(
                select(func.count(ClientResponse.id))
                .join(ClientLink)
                .where(
                    ClientLink.user_id == user_id,
                    ClientResponse.sentiment == sentiment
                )
            ).first()
            sentiment_stats[sentiment] = count or 0
        
        # Get rating breakdown
        rating_stats = {}
        for rating in [1, 2, 3, 4, 5]:
            count = self.db.exec(
                select(func.count(ClientResponse.id))
                .join(ClientLink)
                .where(
                    ClientLink.user_id == user_id,
                    ClientResponse.rating == rating
                )
            ).first()
            rating_stats[f"rating_{rating}"] = count or 0
        
        return {
            "user": {
                "id": user.id,
                "name": user.name,
                "email": user.email,
                "plan": user.plan_type.value,
                "trial_expires_at": user.trial_expires_at.isoformat() if user.trial_expires_at else None,
                "created_at": user.created_at.isoformat() if user.created_at else None
            },
            "usage": usage,
            "limits": plan_info,
            "sentiment_breakdown": sentiment_stats,
            "rating_breakdown": rating_stats,
            "limit_check": self.can_process_more_audio(user_id)
        }
    
    def is_user_active(self, user_id: int) -> bool:
        """
        Check if user is active and can receive services
        """
        user = self.db.exec(
            select(User).where(User.id == user_id)
        ).first()
        
        if not user or not user.is_active:
            return False
        
        # Check if trial expired for free users
        if user.plan_type == PlanType.FREE and user.trial_expires_at:
            if datetime.utcnow() > user.trial_expires_at:
                return False
        
        return True

    async def process_new_feedback(self, response: ClientResponse) -> None:
        """
        Processa um novo feedback recebido
        """
        try:
            # Análise do feedback via OpenAI
            analysis = await self.openai.analyze_feedback(response.transcription)
            
            # Atualiza o registro com a análise
            response.sentiment = analysis["sentiment"]
            response.sentiment_score = analysis["sentiment_score"]
            response.inferred_rating = analysis["inferred_rating"]
            response.emotions = analysis["emotions"]
            response.key_phrases = analysis["key_phrases"]
            response.is_compliment = analysis["is_compliment"]
            response.is_complaint = analysis["is_complaint"]
            response.action_items = analysis["action_items"]
            response.topics = analysis["topics"]
            response.intent_primary = analysis["intent"]["primary"]
            response.intent_secondary = analysis["intent"]["secondary"]
            response.urgency = analysis["urgency"]
            response.satisfaction_level = analysis["customer_satisfaction"]["level"]
            response.satisfaction_reasons = analysis["customer_satisfaction"]["reasons"]
            response.product_mentions = analysis["product_mentions"]
            response.improvement_areas = analysis["improvement_areas"]
            response.processed = True
            
            self.db.add(response)
            await self.db.commit()
            await self.db.refresh(response)
            
        except Exception as e:
            response.processing_error = str(e)
            response.processed = True
            self.db.add(response)
            await self.db.commit()
            
    async def get_dashboard_data(self, user_id: int) -> Dict[str, Any]:
        """
        Retorna dados agregados para o dashboard
        """
        # Busca todos os links do usuário
        links = select(ClientLink.id).where(ClientLink.user_id == user_id)
        link_ids = [link.id for link in self.db.execute(links).scalars().all()]
        
        if not link_ids:
            return self._empty_dashboard_data()
        
        # Busca todos os feedbacks processados
        feedbacks = select(ClientResponse).where(
            ClientResponse.link_id.in_(link_ids),
            ClientResponse.processed == True,
            ClientResponse.processing_error.is_(None)
        )
        responses = self.db.execute(feedbacks).scalars().all()
        
        if not responses:
            return self._empty_dashboard_data()
            
        # Análise dos dados
        compliments = [r for r in responses if r.is_compliment]
        complaints = [r for r in responses if r.is_complaint]
        
        # Calcula média de estrelas
        ratings = [r.inferred_rating for r in responses if r.inferred_rating]
        avg_rating = sum(ratings) / len(ratings) if ratings else 0
        
        # Extrai tópicos para nuvem de palavras
        all_topics = []
        for r in responses:
            all_topics.extend(r.topics)
        topic_counts = Counter(all_topics)
        
        # Coleta todas as emoções
        all_emotions = []
        for r in responses:
            all_emotions.extend(r.emotions)
        emotion_counts = Counter(all_emotions)
        
        # Organiza frases impactantes
        key_phrases = []
        for r in responses:
            for phrase in r.key_phrases:
                key_phrases.append({
                    "text": phrase,
                    "sentiment": r.sentiment,
                    "rating": r.inferred_rating,
                    "urgency": r.urgency
                })
        
        # Agrupa áreas de melhoria
        all_improvements = []
        for r in responses:
            all_improvements.extend(r.improvement_areas)
        improvement_counts = Counter(all_improvements)
        
        # Coleta produtos/serviços mencionados
        all_products = []
        for r in responses:
            all_products.extend(r.product_mentions)
        product_counts = Counter(all_products)
        
        return {
            "summary": {
                "total_feedbacks": len(responses),
                "compliments": len(compliments),
                "complaints": len(complaints),
                "average_rating": round(avg_rating, 1),
                "sentiment_distribution": {
                    "positivo": len([r for r in responses if r.sentiment == "POSITIVO"]),
                    "neutro": len([r for r in responses if r.sentiment == "NEUTRO"]),
                    "negativo": len([r for r in responses if r.sentiment == "NEGATIVO"])
                },
                "urgency_distribution": {
                    "alta": len([r for r in responses if r.urgency == "ALTA"]),
                    "media": len([r for r in responses if r.urgency == "MÉDIA"]),
                    "baixa": len([r for r in responses if r.urgency == "BAIXA"])
                },
                "satisfaction_distribution": {
                    "satisfeito": len([r for r in responses if r.satisfaction_level == "SATISFEITO"]),
                    "neutro": len([r for r in responses if r.satisfaction_level == "NEUTRO"]),
                    "insatisfeito": len([r for r in responses if r.satisfaction_level == "INSATISFEITO"])
                }
            },
            "word_cloud": [
                {"text": topic, "value": count}
                for topic, count in topic_counts.most_common(30)
            ],
            "emotions": [
                {"emotion": emotion, "count": count}
                for emotion, count in emotion_counts.most_common(10)
            ],
            "key_phrases": sorted(
                key_phrases,
                key=lambda x: (x["rating"] if x["rating"] else 0, x["urgency"] == "ALTA"),
                reverse=True
            )[:10],
            "improvement_areas": [
                {"area": area, "count": count}
                for area, count in improvement_counts.most_common(5)
            ],
            "product_mentions": [
                {"product": product, "count": count}
                for product, count in product_counts.most_common(10)
            ],
            "action_items": list(set([
                item for r in responses 
                for item in r.action_items
            ]))[:5]  # Top 5 ações sugeridas
        }
    
    def _empty_dashboard_data(self) -> Dict[str, Any]:
        """
        Retorna estrutura vazia do dashboard
        """
        return {
            "summary": {
                "total_feedbacks": 0,
                "compliments": 0,
                "complaints": 0,
                "average_rating": 0,
                "sentiment_distribution": {
                    "positivo": 0,
                    "neutro": 0,
                    "negativo": 0
                },
                "urgency_distribution": {
                    "alta": 0,
                    "media": 0,
                    "baixa": 0
                },
                "satisfaction_distribution": {
                    "satisfeito": 0,
                    "neutro": 0,
                    "insatisfeito": 0
                }
            },
            "word_cloud": [],
            "emotions": [],
            "key_phrases": [],
            "improvement_areas": [],
            "product_mentions": [],
            "action_items": []
        } 