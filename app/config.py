"""
Configurações da aplicação
"""
import os
from typing import Optional, List
from pydantic import validator, Field
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    # Application Settings
    APP_NAME: str = Field(default="Opina", description="Application name")
    APP_VERSION: str = Field(default="1.0.0", description="Application version")
    APP_DESCRIPTION: str = Field(default="Feedback em áudio com análise de IA", description="Application description")
    APP_URL: str = Field(default="https://app.opina.ai", description="Application URL")
    DEBUG: bool = Field(default=False, description="Debug mode")
    ENVIRONMENT: str = Field(default="development", description="Environment: development, staging, production")
    LOG_LEVEL: str = Field(default="INFO", description="Logging level")
    
    # Security
    SECRET_KEY: str = os.getenv("SECRET_KEY", "your-secret-key-here")
    SESSION_SECRET_KEY: str = os.getenv("SESSION_SECRET_KEY", "your-session-secret-key-here")
    ALLOWED_HOSTS: List[str] = Field(default=["localhost", "127.0.0.1"], description="Allowed hosts for CORS")
    
    # Database
    DATABASE_URL: str = os.getenv("DATABASE_URL", "")
    DATABASE_POOL_SIZE: int = Field(default=10, description="Database connection pool size")
    DATABASE_MAX_OVERFLOW: int = Field(default=20, description="Database connection max overflow")
    
    # Redis (for rate limiting and caching)
    REDIS_URL: str = Field(default="redis://localhost:6379", description="Redis URL")
    
    # WhatsApp/Meta Business API
    WHATSAPP_ACCESS_TOKEN: str = Field(default="", description="WhatsApp Business API access token")
    WHATSAPP_VERIFY_TOKEN: str = Field(default="", description="WhatsApp webhook verify token")
    PHONE_NUMBER_ID: str = Field(default="", description="WhatsApp Business Phone Number ID")
    WHATSAPP_WEBHOOK_URL: str = Field(default="", description="WhatsApp webhook URL")
    
    # Twilio (legacy support)
    TWILIO_ACCOUNT_SID: str = os.getenv("TWILIO_ACCOUNT_SID", "")
    TWILIO_AUTH_TOKEN: str = os.getenv("TWILIO_AUTH_TOKEN", "")
    TWILIO_PHONE_NUMBER: str = os.getenv("TWILIO_PHONE_NUMBER", "")
    TWILIO_WEBHOOK_URL: str = Field(default="", description="Twilio webhook URL")
    
    # External Services
    DEEPGRAM_API_KEY: str = Field(default="", description="Deepgram API key for transcription")
    DEEPGRAM_MODEL: str = Field(default="nova-2", description="Deepgram model")
    DEEPGRAM_LANGUAGE: str = Field(default="pt-BR", description="Deepgram language")
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
    OPENAI_MODEL: str = Field(default="gpt-4o-mini-transcribe", description="OpenAI model for transcription")
    OPENAI_ANALYSIS_MODEL: str = Field(default="gpt-4-turbo-preview", description="OpenAI model for analysis")
    
    # Stripe Payment Processing
    STRIPE_SECRET_KEY: str = os.getenv("STRIPE_SECRET_KEY", "")
    STRIPE_PUBLISHABLE_KEY: str = Field(default="", description="Stripe publishable key")
    STRIPE_WEBHOOK_SECRET: str = os.getenv("STRIPE_WEBHOOK_SECRET", "")
    STRIPE_PRICE_ID_PRO: str = Field(default="", description="Stripe price ID for Pro plan")
    STRIPE_PRICE_ID_ENTERPRISE: str = Field(default="", description="Stripe price ID for Enterprise plan")
    STRIPE_SUCCESS_URL: str = Field(default="https://app.opina.ai/pagamento/sucesso", description="Stripe success URL")
    STRIPE_CANCEL_URL: str = Field(default="https://app.opina.ai/pagamento/cancelado", description="Stripe cancel URL")
    
    # Network Settings
    HOST: str = os.getenv("HOST", "0.0.0.0")
    PORT: int = int(os.getenv("PORT", "8080"))
    
    # Email Settings
    RESEND_API_KEY: str = Field(default="", description="Resend API key")
    FROM_EMAIL: str = Field(default="", description="From email address")
    SUPPORT_EMAIL: str = Field(default="", description="Support email address")
    
    # Custom Webhooks (opcional)
    CUSTOM_WEBHOOK_URL: str = Field(default="", description="Custom webhook URL for notifications")
    WEBHOOK_SECRET: str = Field(default="opina_2025_secure_key", description="Webhook secret for validation")
    
    # Google OAuth
    GOOGLE_CLIENT_ID: str = os.getenv("GOOGLE_CLIENT_ID", "")
    GOOGLE_CLIENT_SECRET: str = os.getenv("GOOGLE_CLIENT_SECRET", "")
    GOOGLE_REDIRECT_URI: str = Field(
        default_factory=lambda: (
            "https://opina-app-xxxxxxxxxxx-rj.a.run.app/auth/google/callback"
            if os.getenv("ENVIRONMENT") == "production"
            else "http://localhost:8000/auth/google/callback"
        )
    )
    
    # JWT Settings
    JWT_SECRET: str = Field(default="", description="JWT Secret Key")
    JWT_ALGORITHM: str = Field(default="HS256", description="JWT Algorithm")
    JWT_EXPIRES_IN: str = Field(default="30d", description="JWT Expiration Time")
    
    # Rate Limiting
    RATE_LIMIT_PER_MINUTE: int = Field(default=60, description="Rate limit per minute per IP")
    RATE_LIMIT_PER_HOUR: int = Field(default=1000, description="Rate limit per hour per IP")
    
    # Business Logic Limits
    FREE_PLAN_AUDIO_LIMIT: int = Field(default=10, description="Audio limit for free plan")
    PRO_PLAN_AUDIO_LIMIT: int = Field(default=100, description="Audio limit for pro plan")
    ENTERPRISE_PLAN_AUDIO_LIMIT: int = Field(default=1000, description="Audio limit for enterprise plan")
    
    # Logging
    LOG_FORMAT: str = Field(default="json", description="Logging format: json or text")
    
    # Monitoring
    SENTRY_DSN: Optional[str] = Field(default=None, description="Sentry DSN for error tracking")
    PROMETHEUS_METRICS_ENABLED: bool = Field(default=True, description="Enable Prometheus metrics")
    
    # Configurações de domínio
    DOMAIN: str = os.getenv("DOMAIN", "localhost:8000")
    
    # Storage
    STORAGE_BUCKET: str
    STORAGE_REGION: str = Field(default="us-east-1", description="Storage region")
    
    @property
    def base_url(self) -> str:
        if self.is_production:
            return f"https://{self.DOMAIN}"
        return f"http://{self.HOST}:{self.PORT}"
    
    @validator("ENVIRONMENT")
    def validate_environment(cls, v):
        allowed = ["development", "staging", "production"]
        if v not in allowed:
            raise ValueError(f"Environment must be one of {allowed}")
        return v
    
    @validator("LOG_LEVEL")
    def validate_log_level(cls, v):
        allowed = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        if v.upper() not in allowed:
            raise ValueError(f"Log level must be one of {allowed}")
        return v.upper()
    
    @validator("ALLOWED_HOSTS", pre=True)
    def parse_allowed_hosts(cls, v):
        if isinstance(v, str):
            return [host.strip() for host in v.split(",")]
        return v
    
    # Computed properties
    @property
    def is_production(self) -> bool:
        return self.ENVIRONMENT == "production"
    
    @property
    def is_development(self) -> bool:
        return self.ENVIRONMENT == "development"
    
    @property
    def CORS_ORIGINS(self) -> List[str]:
        """CORS origins based on environment"""
        if self.is_production:
            return ["https://opina.live"]
        return ["http://localhost:3000", "http://localhost:8000", "http://127.0.0.1:8000"]

    class Config:
        env_file = ".env"
        case_sensitive = True
        extra = "ignore"  # Ignorar campos extras do .env

settings = Settings() 