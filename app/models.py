from datetime import datetime, timedelta
from typing import Optional, List
from enum import Enum
from sqlmodel import SQLModel, Field, Relationship
from sqlalchemy import JSON


# ==============================================
# ENUMS
# ==============================================

class PlanType(str, Enum):
    FREE = "free"
    PRO = "pro"
    ENTERPRISE = "enterprise"

class SubscriptionStatus(str, Enum):
    ACTIVE = "active"
    CANCELED = "canceled"
    PAST_DUE = "past_due"
    INCOMPLETE = "incomplete"

class FeatureType(str, Enum):
    BASIC_AI = "basic_ai"
    ADVANCED_AI = "advanced_ai"
    CUSTOM_AI = "custom_ai"
    SIMPLE_DASHBOARD = "simple_dashboard"
    COMPLETE_DASHBOARD = "complete_dashboard"
    DETAILED_REPORTS = "detailed_reports"
    API_ACCESS = "api_access"
    CUSTOM_INTEGRATIONS = "custom_integrations"

# ==============================================
# PLAN LIMITS CONFIGURATION
# ==============================================

PLAN_LIMITS = {
    PlanType.FREE: {
        "monthly_audios": 5,
        "features": [FeatureType.BASIC_AI, FeatureType.SIMPLE_DASHBOARD],
        "support_hours": None
    },
    PlanType.PRO: {
        "monthly_audios": 15,
        "features": [
            FeatureType.ADVANCED_AI, 
            FeatureType.COMPLETE_DASHBOARD,
            FeatureType.DETAILED_REPORTS
        ],
        "support_hours": 48
    },
    PlanType.ENTERPRISE: {
        "monthly_audios": -1,  # Ilimitado
        "features": [
            FeatureType.CUSTOM_AI,
            FeatureType.COMPLETE_DASHBOARD,
            FeatureType.DETAILED_REPORTS,
            FeatureType.API_ACCESS,
            FeatureType.CUSTOM_INTEGRATIONS
        ],
        "support_hours": 24
    }
}

# ==============================================
# MODELOS PRINCIPAIS
# ==============================================

class UserBase(SQLModel):
    email: str = Field(index=True, unique=True)
    name: str
    google_id: str = Field(index=True, unique=True)
    avatar_url: Optional[str] = None
    
    # Dados da empresa
    company_name: Optional[str] = None
    cnpj: Optional[str] = Field(index=True, default=None)
    
    # Configurações de marca
    brand_color: str = Field(default="#4F46E5")
    logo_url: Optional[str] = None
    welcome_message: str = Field(default="Olá! Deixe seu feedback em áudio:")
    webhook_url: Optional[str] = None
    
    # Controle de plano e pagamento
    plan_type: PlanType = Field(default=PlanType.FREE)
    trial_expires_at: Optional[datetime] = Field(default_factory=lambda: datetime.utcnow() + timedelta(days=7))
    is_active: bool = Field(default=True)
    stripe_customer_id: Optional[str] = Field(index=True, default=None)
    
    # Controle de free tier
    has_used_free_tier: bool = Field(default=False)
    free_tier_started_at: Optional[datetime] = None
    
    # Limites e uso
    max_responses_per_month: int = Field(default=50)
    responses_this_month: int = Field(default=0)
    current_month_audios: int = Field(default=0)
    current_month_start: datetime = Field(default_factory=lambda: datetime.utcnow().replace(day=1, hour=0, minute=0, second=0, microsecond=0))
    last_reset_date: datetime = Field(default_factory=datetime.utcnow)
    
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

class User(UserBase, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    
    # Relacionamentos
    subscriptions: List["Subscription"] = Relationship(back_populates="user")
    client_links: List["ClientLink"] = Relationship(back_populates="user")
    usage_tracking: List["UsageTracking"] = Relationship(back_populates="user")

class SubscriptionBase(SQLModel):
    user_id: int = Field(foreign_key="user.id", index=True)
    stripe_subscription_id: str = Field(index=True, unique=True)
    status: SubscriptionStatus = Field(default=SubscriptionStatus.ACTIVE)
    plan_type: PlanType = Field()
    current_period_start: datetime
    current_period_end: datetime
    canceled_at: Optional[datetime] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

class Subscription(SubscriptionBase, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    
    # Relacionamentos
    user: Optional[User] = Relationship(back_populates="subscriptions")

class ClientLinkBase(SQLModel):
    user_id: int = Field(foreign_key="user.id", index=True)
    link_id: str = Field(index=True, unique=True)  # UUID gerado
    title: str = Field(default="Feedback Request")
    description: Optional[str] = None
    is_active: bool = Field(default=True)
    max_responses: Optional[int] = Field(default=None)  # None = ilimitado
    responses_count: int = Field(default=0)
    views_count: int = Field(default=0)  # Contador de visualizações
    expires_at: Optional[datetime] = None
    
    # Campos de coleta
    collect_name: bool = Field(default=True)
    collect_email: bool = Field(default=True)
    collect_phone: bool = Field(default=True)
    collect_company: bool = Field(default=False)
    collect_rating: bool = Field(default=True)
    
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

class ClientLink(ClientLinkBase, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    
    # Relacionamentos
    user: Optional[User] = Relationship(back_populates="client_links")
    responses: List["ClientResponse"] = Relationship(back_populates="client_link")

class ClientResponseBase(SQLModel):
    link_id: int = Field(foreign_key="clientlink.id", index=True)
    client_name: Optional[str] = None
    client_email: Optional[str] = None
    client_phone: Optional[str] = None
    client_company: Optional[str] = None
    audio_url: Optional[str] = None
    transcription: Optional[str] = None
    rating: Optional[int] = Field(default=None, ge=1, le=5)
    feedback_text: Optional[str] = None
    
    # Campos de análise
    sentiment: Optional[str] = None  # POSITIVO, NEGATIVO, NEUTRO
    
    # Status do processamento
    processed: bool = Field(default=False)
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

class ClientResponse(ClientResponseBase, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    
    # Relacionamentos
    client_link: Optional[ClientLink] = Relationship(back_populates="responses")

class UsageTrackingBase(SQLModel):
    user_id: int = Field(foreign_key="user.id", index=True)
    year: int = Field(index=True)
    month: int = Field(index=True)
    
    # Contadores de uso
    audios_processed: int = Field(default=0)
    basic_ai_calls: int = Field(default=0)
    advanced_ai_calls: int = Field(default=0)
    custom_ai_calls: int = Field(default=0)
    api_calls: int = Field(default=0)
    reports_generated: int = Field(default=0)
    client_links_created: int = Field(default=0)
    
    # Dados de suporte
    support_tickets: int = Field(default=0)
    support_response_time_hours: Optional[float] = None
    
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

class UsageTracking(UsageTrackingBase, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    
    # Relacionamentos
    user: Optional[User] = Relationship(back_populates="usage_tracking")
    
    # Constraint para garantir uma entrada por usuário/mês
    __table_args__ = (
        {"schema": None},
    ) 