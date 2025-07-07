# Opina.live - Voice Feedback Analysis Platform

**Transforme áudios em insights poderosos com IA**

[![Python](https://img.shields.io/badge/Python-3.11-blue.svg)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115-green.svg)](https://fastapi.tiangolo.com)
[![Node.js](https://img.shields.io/badge/Node.js-20+-green.svg)](https://nodejs.org)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-15+-blue.svg)](https://postgresql.org)
[![Google Cloud](https://img.shields.io/badge/Google_Cloud-Run-orange.svg)](https://cloud.google.com/run)

## Table of Contents

- [Overview](#overview)
- [Architecture](#architecture)
- [Business Model](#business-model)
- [Technology Stack](#technology-stack)
- [Data Flow](#data-flow)
- [Deployment](#deployment)
- [Monitoring](#monitoring)
- [Security](#security)
- [Development](#development)

---

## Overview

**Opina.live** é uma plataforma SaaS B2B que permite empresas coletarem e analisarem feedback de clientes através de **mensagens de áudio via WhatsApp**, utilizando **Inteligência Artificial** para transcrição automática e análise de sentimentos.

### Key Features

- **WhatsApp Integration**: Coleta via interface familiar aos clientes
- **AI-Powered Analysis**: OpenAI Whisper + GPT-4 para insights profundos
- **Real-time Dashboard**: Visualização intuitiva de dados e tendências
- **Subscription Management**: Planos flexíveis com Stripe
- **Enterprise Security**: Google OAuth + LGPD compliance
- **Advanced Analytics**: Sentiment, topics, urgency, action items

### Target Market

- **Empresas B2C** que precisam de feedback qualitativo
- **Restaurantes, hotéis, consultórios** com alto volume de atendimento
- **E-commerce** buscando insights além de ratings numéricos
- **Equipes de CX** que querem automatizar análise de feedback

---

## Architecture

### High-Level Architecture

```mermaid
graph TB
    subgraph "Client Layer"
        U[Usuários/Empresas]
        C[Clientes Finais]
        WA[WhatsApp Web]
    end

    subgraph "Presentation Layer"
        LP[Landing Page]
        AUTH[Login/Register]
        DASH[Dashboard]
        API[REST API]
    end

    subgraph "Application Layer"
        subgraph "FastAPI Backend"
            ROUTES[Routes Layer]
            AUTH_SVC[Auth Service]
            BIZ_SVC[Business Service]
            USAGE_SVC[Usage Service]
            AI_SVC[AI Services]
        end
        
        subgraph "WhatsApp Integration"
            BAILEYS[Baileys Node.js]
            WA_SVC[WhatsApp Service]
        end
    end

    subgraph "External Services"
        GOOGLE[Google OAuth]
        STRIPE[Stripe Payments]
        OPENAI[OpenAI API]
        NEON[Neon PostgreSQL]
    end

    subgraph "Infrastructure"
        GCR[Google Cloud Run]
        PROM[Prometheus]
        GRAF[Grafana]
    end

    %% User interactions
    U --> LP
    U --> AUTH
    U --> DASH
    C --> WA
    
    %% Authentication flow
    AUTH --> GOOGLE
    AUTH --> AUTH_SVC
    
    %% Dashboard interactions
    DASH --> API
    API --> ROUTES
    
    %% WhatsApp flow
    WA --> BAILEYS
    BAILEYS --> WA_SVC
    WA_SVC --> BIZ_SVC
    
    %% Business logic
    ROUTES --> AUTH_SVC
    ROUTES --> BIZ_SVC
    ROUTES --> USAGE_SVC
    BIZ_SVC --> AI_SVC
    
    %% External integrations
    AUTH_SVC --> GOOGLE
    BIZ_SVC --> STRIPE
    AI_SVC --> OPENAI
    
    %% Data persistence
    AUTH_SVC --> NEON
    BIZ_SVC --> NEON
    USAGE_SVC --> NEON
    
    %% Monitoring
    GCR --> PROM
    PROM --> GRAF
    
    %% Deployment
    ROUTES --> GCR
    BAILEYS --> GCR
```

### Core Components

#### **1. FastAPI Backend (Python 3.11)**
- **Routes**: RESTful API endpoints for web and mobile
- **Services**: Business logic, authentication, AI processing
- **Models**: SQLModel for type-safe database operations
- **Middleware**: CORS, rate limiting, usage tracking

#### **2. WhatsApp Integration (Node.js)**
- **Baileys Library**: WhatsApp Web API client
- **Real-time Processing**: Audio message capture and forwarding
- **Session Management**: Persistent authentication with QR codes
- **Error Recovery**: Automatic reconnection and cleanup

#### **3. Database Layer (PostgreSQL)**
- **Users & Authentication**: Google OAuth integration
- **Subscription Management**: Stripe integration for billing
- **Feedback Processing**: Audio metadata and AI analysis results
- **Usage Tracking**: Plan limits and feature access control

#### **4. AI Processing Pipeline**
- **OpenAI Whisper**: Audio transcription (Portuguese optimized)
- **GPT-4**: Advanced sentiment analysis and topic extraction
- **Business Intelligence**: Action items, urgency levels, satisfaction scoring

---

## Business Model

### Subscription Tiers

| Plan | Monthly Audios | Price | Key Features |
|------|---------------|-------|--------------|
| **Free** | 5 audios | R$ 0 | Basic dashboard, sentiment analysis |
| **Pro** | 15 audios | R$ 29 | Advanced analytics, reports, priority support |
| **Enterprise** | Unlimited | Custom | API access, custom integrations, dedicated support |

### Usage Controls & Guardrails

```python
PLAN_LIMITS = {
    PlanType.FREE: {
        "monthly_audios": 5,
        "features": [FeatureType.BASIC_AI, FeatureType.SIMPLE_DASHBOARD]
    },
    PlanType.PRO: {
        "monthly_audios": 15,
        "features": [FeatureType.ADVANCED_AI, FeatureType.DETAILED_REPORTS]
    },
    PlanType.ENTERPRISE: {
        "monthly_audios": -1,  # Unlimited
        "features": [FeatureType.CUSTOM_AI, FeatureType.API_ACCESS]
    }
}
```

### Revenue Streams

1. **Monthly Subscriptions** (Primary) - Recurring SaaS revenue
2. **Usage Overages** (Pro+) - Additional audio processing beyond limits
3. **Custom Integrations** (Enterprise) - Professional services
4. **White-label Solutions** (Future) - Platform licensing

---

## Technology Stack

### **Backend**
- **FastAPI** 0.115+ - Modern, fast Python web framework
- **SQLModel** - Type-safe ORM with Pydantic integration
- **Alembic** - Database migrations
- **Pydantic** - Data validation and settings management

### **Authentication & Payments**
- **Google OAuth 2.0** - User authentication
- **PyJWT** - Session management
- **Stripe** - Payment processing and subscription management
- **bcrypt** - Password hashing (if needed)

### **AI & External Services**
- **OpenAI API** - Whisper (transcription) + GPT-4 (analysis)
- **Baileys** - WhatsApp Web API client
- **httpx/aiohttp** - Async HTTP clients

### **Database & Infrastructure**
- **PostgreSQL 15+** (Neon.tech) - Primary database
- **Google Cloud Run** - Serverless deployment
- **Prometheus + Grafana** - Monitoring and metrics
- **Docker** - Containerization

### **Development & Tooling**
- **Python 3.11** - Latest stable Python
- **Node.js 20+** - For WhatsApp integration
- **pytest** - Testing framework
- **Black + Ruff** - Code formatting and linting

---

## Data Flow

### Feedback Processing Pipeline

```mermaid
sequenceDiagram
    participant C as Cliente Final
    participant WA as WhatsApp
    participant B as Baileys Listener
    participant P as Python Backend
    participant AI as OpenAI
    participant DB as PostgreSQL
    participant U as Usuário Empresa

    Note over C, U: Fluxo de Processamento de Feedback

    %% 1. Configuração inicial
    U->>P: Cria link de feedback
    P->>DB: Salva ClientLink
    P-->>U: Retorna link único

    %% 2. Cliente envia áudio
    C->>WA: Envia mensagem de áudio
    WA->>B: Webhook com áudio
    B->>B: Download do áudio
    B->>P: POST /webhooks/process-audio

    %% 3. Processamento
    P->>DB: Cria ClientResponse
    P->>AI: Transcreve áudio (Whisper)
    AI-->>P: Texto transcrito
    P->>AI: Analisa sentimento (GPT-4)
    AI-->>P: Análise completa
    P->>DB: Salva análise

    %% 4. Notificação
    P-->>U: Webhook customizado (opcional)
    U->>P: Consulta dashboard
    P->>DB: Busca análises
    DB-->>P: Dados processados
    P-->>U: Dashboard atualizado

    Note over P, AI: Análise inclui: sentimento, rating, tópicos, urgência, ações recomendadas
```

### Database Schema

```mermaid
erDiagram
    User {
        int id PK
        string email UK
        string name
        string google_id UK
        string company_name
        string cnpj
        enum plan_type
        datetime trial_expires_at
        boolean is_active
        string stripe_customer_id
        int current_month_audios
        datetime created_at
    }

    Subscription {
        int id PK
        int user_id FK
        string stripe_subscription_id UK
        enum status
        enum plan_type
        datetime current_period_start
        datetime current_period_end
        datetime canceled_at
    }

    ClientLink {
        int id PK
        int user_id FK
        string link_token UK
        string context
        boolean is_active
        datetime created_at
    }

    ClientResponse {
        int id PK
        int link_id FK
        string client_hash
        string audio_url
        text transcription
        string sentiment
        float sentiment_score
        int inferred_rating
        json emotions
        json key_phrases
        json action_items
        json topics
        string urgency
        boolean processed
        datetime created_at
    }

    UsageTracking {
        int id PK
        int user_id FK
        int basic_ai_calls
        int advanced_ai_calls
        int custom_ai_calls
        int audios_processed
        datetime month_start
    }

    User ||--o{ Subscription : "has"
    User ||--o{ ClientLink : "creates"
    User ||--o{ UsageTracking : "tracks"
    ClientLink ||--o{ ClientResponse : "receives"
```

---

## Deployment

### Infrastructure Overview

```mermaid
graph TB
    subgraph "Google Cloud Platform"
        subgraph "Cloud Run"
            MAIN[Opina API<br/>FastAPI + Node.js]
            ENV[Environment Variables]
        end
        
        subgraph "Cloud Build"
            BUILD[Automated Build]
            DOCKER[Docker Container]
        end
    end

    subgraph "External Services"
        NEON[Neon PostgreSQL<br/>São Paulo Region]
        GOOGLE_OAUTH[Google OAuth 2.0]
        STRIPE_API[Stripe API<br/>Payment Processing]
        OPENAI_API[OpenAI API<br/>Whisper + GPT-4]
    end

    subgraph "Monitoring Stack"
        PROM[Prometheus<br/>Metrics Collection]
        GRAF[Grafana<br/>Dashboards]
        ALERTS[Alert Manager<br/>Email Notifications]
    end

    subgraph "WhatsApp Integration"
        WA_WEB[WhatsApp Web<br/>QR Code Auth]
        BAILEYS[Baileys Library<br/>Node.js Process]
    end

    subgraph "Development"
        REPO[Git Repository]
        LOCAL[Local Development<br/>Docker Compose]
    end

    %% Build & Deploy Flow
    REPO --> BUILD
    BUILD --> DOCKER
    DOCKER --> MAIN

    %% Runtime Dependencies
    MAIN --> NEON
    MAIN --> GOOGLE_OAUTH
    MAIN --> STRIPE_API
    MAIN --> OPENAI_API
    
    %% WhatsApp Integration
    BAILEYS --> WA_WEB
    MAIN --> BAILEYS

    %% Monitoring
    MAIN --> PROM
    PROM --> GRAF
    PROM --> ALERTS

    %% Configuration
    ENV --> MAIN

    %% Development Flow
    LOCAL --> REPO

    style MAIN fill:#e1f5fe
    style NEON fill:#f3e5f5
    style OPENAI_API fill:#fff3e0
    style STRIPE_API fill:#e8f5e8
```

### Production Configuration

```bash
# Core Application
ENVIRONMENT=production
DEBUG=False
HOST=0.0.0.0
PORT=8080
DOMAIN=opina.live

# Database
DATABASE_URL=postgresql://neondb_owner:...@ep-curly-credit.sa-east-1.aws.neon.tech/neondb

# Authentication
GOOGLE_CLIENT_ID=856246905710-...
GOOGLE_CLIENT_SECRET=GOCSPX-...
SECRET_KEY=opina-production-secret-key-2025-secure

# AI Services
OPENAI_API_KEY=sk-proj-...
OPENAI_MODEL=whisper-1

# Payments
STRIPE_SECRET_KEY=sk_live_...
STRIPE_PUBLISHABLE_KEY=pk_live_...
STRIPE_WEBHOOK_SECRET=whsec_...

# Business Rules
FREE_PLAN_AUDIO_LIMIT=5
PRO_PLAN_AUDIO_LIMIT=15
ENTERPRISE_PLAN_AUDIO_LIMIT=1000
```

### Deployment Commands

```bash
# Local Development
./dev.sh                    # Start local environment
uvicorn app.main:app --reload --port 8000

# WhatsApp Service
cd whatsapp && npm install && node baileys-listener.js

# Production Deployment
gcloud builds submit --config cloudbuild.yaml
gcloud run deploy opina-app --region us-central1
```

---

## Monitoring

### Health Checks

```bash
# Basic health check
GET /health

# Detailed health check with dependencies
GET /health/detailed

# Kubernetes probes
GET /health/ready   # Readiness probe
GET /health/live    # Liveness probe
```

### Key Metrics

- **WhatsApp Connection Status**: Real-time connectivity monitoring
- **Audio Processing Rate**: Messages/minute, success rate
- **API Response Times**: P95, P99 latencies
- **Database Performance**: Query times, connection pooling
- **Business Metrics**: Active users, conversion rates, revenue

### Alerting Rules

```yaml
# High error rate (>20% in 15min)
- alert: HighErrorRate
  expr: rate(audio_processing_total{status="error"}[15m]) / 
        rate(audio_processing_total[15m]) > 0.2

# WhatsApp disconnected (>5min)
- alert: WhatsAppDisconnected
  expr: whatsapp_connection_status == 0
  for: 5m

# Slow processing (>2min average)
- alert: SlowProcessing
  expr: rate(audio_processing_duration_seconds_sum[5m]) / 
        rate(audio_processing_duration_seconds_count[5m]) > 120
```

---

## Security

### Authentication & Authorization

- **Google OAuth 2.0**: Enterprise-grade authentication
- **JWT Tokens**: Stateless session management (30-day expiry)
- **Role-based Access**: Plan-based feature restrictions
- **CORS Configuration**: Environment-specific origins

### Data Protection

- **LGPD Compliance**: Brazilian data protection regulations
- **Data Encryption**: TLS 1.3 for all communications
- **Anonymization**: Client data hashed for privacy
- **Audit Logging**: Structured logs for compliance

### Input Validation & Rate Limiting

```python
# Usage guardrails per plan
@usage_middleware
async def check_audio_limit(user: User):
    if user.current_month_audios >= plan_limits[user.plan_type]:
        raise UsageError("Monthly audio limit exceeded")

# Rate limiting per IP
@rate_limit("60/minute")
async def api_endpoint():
    pass
```

---

## Development

### Project Structure

```
opina-live/
├── CORE APPLICATION
│   ├── app/main.py              # FastAPI app setup
│   ├── app/config.py            # Settings management
│   ├── app/database.py          # Database connection
│   ├── app/models.py            # SQLModel definitions
│   └── app/dependencies.py     # Shared dependencies
│
├── AUTHENTICATION
│   ├── app/routes/auth.py       # OAuth routes
│   └── app/services/auth.py     # Auth business logic
│
├── CORE FEATURES
│   ├── app/routes/feedback.py   # Feedback processing
│   ├── app/routes/webhooks.py   # WhatsApp webhooks
│   ├── app/routes/payments.py   # Stripe integration
│   └── app/routes/health.py     # Health checks
│
├── SERVICES
│   ├── app/services/business.py     # Business logic
│   ├── app/services/transcription.py # OpenAI Whisper
│   ├── app/services/openai.py       # GPT-4 analysis
│   ├── app/services/whatsapp.py     # WhatsApp integration
│   ├── app/services/payment.py      # Stripe services
│   ├── app/services/usage.py        # Usage tracking
│   └── app/services/monitoring.py   # Metrics collection
│
├── WHATSAPP INTEGRATION
│   ├── whatsapp/baileys-listener.js # WhatsApp client
│   ├── whatsapp/package.json        # Node.js dependencies
│   └── auth/                        # Runtime auth files
│
└── FRONTEND
    └── app/templates/               # HTML templates
        ├── index.html               # Landing page
        ├── dashboard.html           # Main dashboard
        └── login.html               # Authentication
```

### Development Setup

```bash
# 1. Clone repository
git clone https://github.com/company/opina-live.git
cd opina-live

# 2. Set up Python environment
python3.11 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# 3. Configure environment
cp config-local.env .env
# Edit .env with your API keys

# 4. Set up Node.js for WhatsApp
cd whatsapp
npm install
cd ..

# 5. Initialize database
alembic upgrade head

# 6. Start development servers
./dev.sh  # Starts both Python and Node.js services
```

### Testing

```bash
# Run test suite
pytest

# Test authentication flow
python test-auth.py

# Manual API testing
curl http://localhost:8000/health/detailed
```

### Code Quality

```bash
# Format code
black app/
ruff check app/

# Type checking
mypy app/

# Security scanning
bandit -r app/
```

---

## API Documentation

### Core Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/` | Landing page |
| `GET` | `/dashboard` | Main dashboard |
| `POST` | `/auth/google` | Start Google OAuth |
| `GET` | `/auth/google/callback` | OAuth callback |
| `POST` | `/feedback/process` | Process audio feedback |
| `GET` | `/api/dashboard/stats` | Dashboard statistics |
| `POST` | `/payments/create-subscription` | Create Stripe subscription |
| `GET` | `/health/detailed` | Comprehensive health check |

### Webhook Integration

```python
# Custom webhook for real-time notifications
POST /your-webhook-endpoint
{
    "event": "feedback_processed",
    "link_id": "abc123",
    "response": {
        "transcription": "Produto excelente!",
        "sentiment": "positivo",
        "rating": 5,
        "urgency": "baixa",
        "action_items": ["Manter qualidade"]
    }
}
```

---

## Roadmap

### Q1 2025 - Core Stability
- [ ] Enhanced monitoring and alerting
- [ ] Automated testing suite
- [ ] Performance optimizations
- [ ] Advanced analytics dashboard

### Q2 2025 - Scale & Features
- [ ] Multi-language support (English, Spanish)
- [ ] WhatsApp Business API migration
- [ ] Advanced AI insights (emotion detection)
- [ ] CRM integrations (HubSpot, Salesforce)

### Q3 2025 - Enterprise
- [ ] White-label solutions
- [ ] Advanced API endpoints
- [ ] Custom ML model training
- [ ] Multi-region deployment

### Q4 2025 - Innovation
- [ ] Real-time audio analysis
- [ ] Video feedback support
- [ ] AI-powered response suggestions
- [ ] Predictive analytics

---

## License

**Proprietary** - All rights reserved to Opina Tecnologia Ltda.

---

## Contributing

This is a proprietary project. For internal development guidelines and contribution processes, please refer to the internal documentation or contact the development team.

---

## Support

- **Technical Issues**: [GitHub Issues](https://github.com/company/opina-live/issues)
- **Business Inquiries**: contato@opina.live
- **Emergency Support**: WhatsApp +55 (11) 99999-9999

---

## Code Cleanup & Maintenance

### Files to Review/Remove

#### **1. Unused/Development Files**
```bash
# Empty directories (safe to ignore)
audios/                    # Storage directory - empty in development
auth/                      # WhatsApp session files - runtime generated

# Development/Testing Files
test-auth.py              # Development testing script (keep for debugging)
env.yaml                  # Untracked - likely deprecated configuration
env.development           # Legacy environment file (prefer config-local.env)
env.template              # Redundant with config-local.env

# Documentation
DOCUMENTOS_LEGAIS.md      # Legal docs - business use, not engineering
GOOGLE_OAUTH_SETUP.md     # Setup guide - may need update
SETUP_GUIDE.md            # Legacy setup guide (replaced by this README)
```

#### **2. Migration Files**
```bash
migrations/versions/payment_system.py    # Single migration - consider squashing when stable
```

#### **3. Configuration Consolidation**
Current configuration files:
-  `config-local.env` - **KEEP** (primary development config)
-  `env.template` - **REMOVE** (redundant)
-  `env.development` - **REMOVE** (legacy)
-  `env.yaml` - **REMOVE** (untracked/unused)

### Recommended Cleanup Actions

```bash
# Remove redundant environment files
rm -f env.template env.development env.yaml

# Clean up documentation (optional)
rm -f DOCUMENTOS_LEGAIS.md GOOGLE_OAUTH_SETUP.md SETUP_GUIDE.md

# Ensure correct permissions for runtime directories
chmod 755 audios/ auth/
```

### Architecture Notes for Staff Engineers

#### **Critical Dependencies**
- **Google Cloud Run**: Single point of deployment
- **Neon PostgreSQL**: Database - no local backup strategy
- **OpenAI API**: Core business logic - no fallback
- **Baileys Library**: WhatsApp integration - frequent breaking changes

#### **Technical Debt**
1. **WhatsApp Integration**: Using unofficial API (Baileys) - consider Business API migration
2. **No Automated Testing**: Critical flows lack test coverage
3. **Mixed Languages**: Python + Node.js increases complexity
4. **Single Tenant**: Each deployment handles one WhatsApp number
5. **No Local Database**: All development uses remote Neon DB

#### **Scalability Concerns**
- **File Storage**: No persistent audio storage configured
- **Rate Limiting**: Basic implementation, needs enterprise-grade solution
- **Session Management**: WhatsApp sessions stored locally, not persistent
- **Database Migrations**: Manual process, no CI/CD integration

#### **Security Review Needed**
- **Environment Variables**: Scattered across multiple files
- **JWT Secret**: Single secret for all environments
- **CORS**: Broad permissions in development
- **Error Handling**: Potential information leakage in production logs

---
