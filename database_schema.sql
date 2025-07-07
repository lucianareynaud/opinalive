-- ==============================================
-- OPINA - SCHEMA LIMPO (SEM GOOGLE SHEETS)
-- ==============================================

-- 1. USUÁRIOS (nossos clientes - empresas)
CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY,
    email VARCHAR(255) UNIQUE NOT NULL,
    name VARCHAR(255) NOT NULL,
    company_name VARCHAR(255),
    google_id VARCHAR(255) UNIQUE NOT NULL,
    avatar_url TEXT,
    plan_type VARCHAR(20) DEFAULT 'free' CHECK (plan_type IN ('free', 'pro', 'enterprise')),
    trial_expires_at TIMESTAMP WITH TIME ZONE DEFAULT (NOW() + INTERVAL '7 days'),
    is_active BOOLEAN DEFAULT TRUE,
    
    -- Integração externa
    stripe_customer_id VARCHAR(255),
    webhook_url TEXT, -- URL personalizada para receber dados (opcional)
    
    -- Configurações do cliente
    brand_color VARCHAR(7) DEFAULT '#4F46E5',
    logo_url TEXT,
    welcome_message TEXT DEFAULT 'Olá! Deixe seu feedback em áudio:',
    
    -- Limites baseados no plano
    max_responses_per_month INTEGER DEFAULT 50,
    responses_this_month INTEGER DEFAULT 0,
    
    -- Controle
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- 2. LINKS DE FEEDBACK (identificação automática)
CREATE TABLE IF NOT EXISTS feedback_links (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    
    -- IDENTIFICAÇÃO ÚNICA (token automático)
    link_token VARCHAR(32) UNIQUE NOT NULL, -- Token único: a1b2c3d4e5f6...
    slug VARCHAR(255), -- nome-personalizado (opcional)
    
    -- URL completa: opina.live/f/a1b2c3d4e5f6
    -- Cliente final clica → sistema automaticamente sabe que é do user_id
    
    -- Configurações do link
    title VARCHAR(255) DEFAULT 'Feedback Request',
    description TEXT,
    is_active BOOLEAN DEFAULT TRUE,
    
    -- Limites por link
    max_responses INTEGER, -- NULL = ilimitado
    responses_count INTEGER DEFAULT 0,
    expires_at TIMESTAMP WITH TIME ZONE,
    
    -- Configurações de coleta
    collect_name BOOLEAN DEFAULT TRUE,
    collect_email BOOLEAN DEFAULT TRUE,
    collect_phone BOOLEAN DEFAULT TRUE,
    collect_company BOOLEAN DEFAULT FALSE,
    collect_rating BOOLEAN DEFAULT TRUE,
    
    -- Métricas
    views_count INTEGER DEFAULT 0,
    conversion_rate DECIMAL(5,2) DEFAULT 0.00,
    
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- 3. RESPOSTAS DOS CLIENTES FINAIS (tabela principal)
CREATE TABLE IF NOT EXISTS feedback_responses (
    id SERIAL PRIMARY KEY,
    link_id INTEGER NOT NULL REFERENCES feedback_links(id) ON DELETE CASCADE,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE, -- Denormalizado para performance
    
    -- Identificação do cliente final
    client_name VARCHAR(255),
    client_email VARCHAR(255),
    client_phone VARCHAR(255),
    client_company VARCHAR(255),
    
    -- Dados do feedback
    audio_url TEXT,
    audio_duration INTEGER, -- em segundos
    transcription TEXT,
    rating INTEGER CHECK (rating >= 1 AND rating <= 5),
    feedback_text TEXT,
    
    -- ============================================
    -- ANÁLISE DE IA POR PLANO
    -- ============================================
    
    -- FREE: Análise básica
    sentiment_basic VARCHAR(50), -- "positivo", "negativo", "neutro"
    
    -- PRO: Análise avançada (apenas para planos pagos)
    sentiment_score DECIMAL(3,2), -- Score detalhado (-1.0 a 1.0)
    emotions JSONB, -- {"joy": 0.8, "anger": 0.2, "fear": 0.1}
    topics JSONB, -- ["atendimento", "produto", "preço"]
    keywords JSONB, -- ["excelente", "demora", "caro"]
    intent VARCHAR(100), -- "reclamação", "elogio", "sugestão"
    priority_level VARCHAR(20), -- "baixa", "média", "alta", "crítica"
    
    -- ENTERPRISE: Análise completa
    business_insights JSONB, -- Insights de negócio
    competitor_mentions JSONB, -- Menções a concorrentes
    product_features JSONB, -- Features mencionadas
    improvement_suggestions JSONB, -- Sugestões de melhoria
    customer_journey_stage VARCHAR(50), -- "awareness", "consideration", "decision"
    
    -- Controle de análise
    analysis_version VARCHAR(20) DEFAULT 'v1.0',
    analysis_completed_at TIMESTAMP WITH TIME ZONE,
    
    -- Controle de processamento
    processed BOOLEAN DEFAULT FALSE,
    
    -- Metadados
    ip_address INET,
    user_agent TEXT,
    referrer TEXT,
    device_type VARCHAR(20), -- mobile, desktop, tablet
    
    -- Particionamento (para 1M+ registros)
    created_month INTEGER GENERATED ALWAYS AS (EXTRACT(YEAR FROM created_at) * 100 + EXTRACT(MONTH FROM created_at)) STORED,
    
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- 4. ASSINATURAS (Stripe)
CREATE TABLE IF NOT EXISTS subscriptions (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    stripe_subscription_id VARCHAR(255) UNIQUE NOT NULL,
    status VARCHAR(20) DEFAULT 'active' CHECK (status IN ('active', 'canceled', 'past_due', 'incomplete')),
    plan_type VARCHAR(20) NOT NULL CHECK (plan_type IN ('pro', 'enterprise')),
    current_period_start TIMESTAMP WITH TIME ZONE NOT NULL,
    current_period_end TIMESTAMP WITH TIME ZONE NOT NULL,
    canceled_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- ==============================================
-- ÍNDICES PARA PERFORMANCE (1M+ registros)
-- ==============================================

-- Usuários
CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);
CREATE INDEX IF NOT EXISTS idx_users_google_id ON users(google_id);
CREATE INDEX IF NOT EXISTS idx_users_plan_type ON users(plan_type);
CREATE INDEX IF NOT EXISTS idx_users_active ON users(is_active);

-- Links de feedback (CRÍTICO para identificação)
CREATE INDEX IF NOT EXISTS idx_feedback_links_user_id ON feedback_links(user_id);
CREATE INDEX IF NOT EXISTS idx_feedback_links_token ON feedback_links(link_token); -- Para identificação rápida
CREATE INDEX IF NOT EXISTS idx_feedback_links_active ON feedback_links(is_active);

-- Respostas (CRÍTICO para performance)
CREATE INDEX IF NOT EXISTS idx_feedback_responses_link_id ON feedback_responses(link_id);
CREATE INDEX IF NOT EXISTS idx_feedback_responses_user_id ON feedback_responses(user_id);
CREATE INDEX IF NOT EXISTS idx_feedback_responses_created_at ON feedback_responses(created_at);
CREATE INDEX IF NOT EXISTS idx_feedback_responses_processed ON feedback_responses(processed);
CREATE INDEX IF NOT EXISTS idx_feedback_responses_month ON feedback_responses(created_month);

-- Índices compostos para queries comuns
CREATE INDEX IF NOT EXISTS idx_responses_user_month ON feedback_responses(user_id, created_month);
CREATE INDEX IF NOT EXISTS idx_responses_link_processed ON feedback_responses(link_id, processed);

-- Assinaturas
CREATE INDEX IF NOT EXISTS idx_subscriptions_user_id ON subscriptions(user_id);
CREATE INDEX IF NOT EXISTS idx_subscriptions_stripe_id ON subscriptions(stripe_subscription_id);

-- ==============================================
-- TRIGGERS E FUNÇÕES
-- ==============================================

-- Função para atualizar updated_at
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Função para incrementar contador de respostas
CREATE OR REPLACE FUNCTION increment_response_counters()
RETURNS TRIGGER AS $$
BEGIN
    -- Incrementa contador no link
    UPDATE feedback_links 
    SET responses_count = responses_count + 1,
        updated_at = NOW()
    WHERE id = NEW.link_id;
    
    -- Incrementa contador mensal do usuário
    UPDATE users 
    SET responses_this_month = responses_this_month + 1,
        updated_at = NOW()
    WHERE id = NEW.user_id;
    
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Função para incrementar views
CREATE OR REPLACE FUNCTION increment_view_counter()
RETURNS TRIGGER AS $$
BEGIN
    UPDATE feedback_links 
    SET views_count = views_count + 1,
        updated_at = NOW()
    WHERE link_token = NEW.link_token;
    
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Triggers
CREATE TRIGGER update_users_updated_at BEFORE UPDATE ON users FOR EACH ROW EXECUTE PROCEDURE update_updated_at_column();
CREATE TRIGGER update_feedback_links_updated_at BEFORE UPDATE ON feedback_links FOR EACH ROW EXECUTE PROCEDURE update_updated_at_column();
CREATE TRIGGER update_feedback_responses_updated_at BEFORE UPDATE ON feedback_responses FOR EACH ROW EXECUTE PROCEDURE update_updated_at_column();
CREATE TRIGGER increment_counters_on_response AFTER INSERT ON feedback_responses FOR EACH ROW EXECUTE PROCEDURE increment_response_counters();

-- ==============================================
-- VIEWS PARA ANALYTICS
-- ==============================================

-- View para dashboard do usuário
CREATE OR REPLACE VIEW user_dashboard_stats AS
SELECT 
    u.id,
    u.name,
    u.company_name,
    u.plan_type,
    u.responses_this_month,
    u.max_responses_per_month,
    COUNT(fl.id) as total_links,
    COUNT(CASE WHEN fl.is_active THEN 1 END) as active_links,
    COALESCE(SUM(fl.responses_count), 0) as total_responses,
    COALESCE(SUM(fl.views_count), 0) as total_views,
    CASE 
        WHEN SUM(fl.views_count) > 0 THEN 
            ROUND((COALESCE(SUM(fl.responses_count), 0) * 100.0 / SUM(fl.views_count)), 2)
        ELSE 0 
    END as overall_conversion_rate
FROM users u
LEFT JOIN feedback_links fl ON u.id = fl.user_id
GROUP BY u.id, u.name, u.company_name, u.plan_type, u.responses_this_month, u.max_responses_per_month;

-- ==============================================
-- COMENTÁRIOS PARA DOCUMENTAÇÃO
-- ==============================================

COMMENT ON TABLE users IS 'Clientes da Opina (empresas que usam o sistema)';
COMMENT ON TABLE feedback_links IS 'Links únicos com tokens para identificação automática';
COMMENT ON TABLE feedback_responses IS 'Respostas dos clientes finais (tabela principal)';
COMMENT ON TABLE subscriptions IS 'Assinaturas pagas via Stripe';

COMMENT ON COLUMN feedback_links.link_token IS 'Token único para identificação automática (a1b2c3d4e5f6...)';
COMMENT ON COLUMN feedback_responses.created_month IS 'Mês da criação para particionamento (YYYYMM)';
COMMENT ON COLUMN feedback_responses.sentiment_score IS 'Score de sentimento de -1.0 (negativo) a 1.0 (positivo)'; 