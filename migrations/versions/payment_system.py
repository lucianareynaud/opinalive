"""Payment system and user table consolidation

Revision ID: payment_system
Revises: initial
Create Date: 2024-03-21

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'payment_system'
down_revision = 'initial'
branch_labels = None
depends_on = None

def upgrade():
    # Criar enum para status de assinatura
    op.execute("CREATE TYPE subscription_status AS ENUM ('active', 'canceled', 'past_due', 'incomplete')")
    
    # Criar enum para tipo de plano
    op.execute("CREATE TYPE plan_type AS ENUM ('free', 'pro', 'enterprise')")
    
    # Adicionar novos campos na tabela users
    op.add_column('users', sa.Column('cnpj', sa.String(length=14), nullable=True))
    op.add_column('users', sa.Column('has_used_free_tier', sa.Boolean(), nullable=False, server_default='false'))
    op.add_column('users', sa.Column('free_tier_started_at', sa.TIMESTAMP(timezone=True), nullable=True))
    op.add_column('users', sa.Column('current_month_audios', sa.Integer(), nullable=False, server_default='0'))
    op.add_column('users', sa.Column('current_month_start', sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("date_trunc('month', CURRENT_TIMESTAMP)")))
    op.add_column('users', sa.Column('last_reset_date', sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')))
    
    # Criar índices importantes
    op.create_index('ix_users_email', 'users', ['email'], unique=True)
    op.create_index('ix_users_google_id', 'users', ['google_id'], unique=True)
    op.create_index('ix_users_stripe_customer_id', 'users', ['stripe_customer_id'], unique=True)
    op.create_index('ix_users_cnpj', 'users', ['cnpj'])
    
    # Criar tabela de assinaturas
    op.create_table(
        'subscriptions',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('stripe_subscription_id', sa.String(), nullable=False),
        sa.Column('status', postgresql.ENUM('active', 'canceled', 'past_due', 'incomplete', name='subscription_status'), nullable=False),
        sa.Column('plan_type', postgresql.ENUM('free', 'pro', 'enterprise', name='plan_type'), nullable=False),
        sa.Column('current_period_start', sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column('current_period_end', sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column('canceled_at', sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('updated_at', sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Criar índices para assinaturas
    op.create_index('ix_subscriptions_user_id', 'subscriptions', ['user_id'])
    op.create_index('ix_subscriptions_stripe_subscription_id', 'subscriptions', ['stripe_subscription_id'], unique=True)
    
    # Criar tabela de tracking de uso
    op.create_table(
        'usage_tracking',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('year', sa.Integer(), nullable=False),
        sa.Column('month', sa.Integer(), nullable=False),
        sa.Column('audios_processed', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('basic_ai_calls', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('advanced_ai_calls', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('custom_ai_calls', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('api_calls', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('reports_generated', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('client_links_created', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('support_tickets', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('support_response_time_hours', sa.Float(), nullable=True),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('updated_at', sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Criar índices para tracking de uso
    op.create_index('ix_usage_tracking_user_id', 'usage_tracking', ['user_id'])
    op.create_index('ix_usage_tracking_year_month', 'usage_tracking', ['year', 'month'])

def downgrade():
    # Remover tabelas
    op.drop_table('usage_tracking')
    op.drop_table('subscriptions')
    
    # Remover colunas adicionadas
    op.drop_column('users', 'cnpj')
    op.drop_column('users', 'has_used_free_tier')
    op.drop_column('users', 'free_tier_started_at')
    op.drop_column('users', 'current_month_audios')
    op.drop_column('users', 'current_month_start')
    op.drop_column('users', 'last_reset_date')
    
    # Remover enums
    op.execute('DROP TYPE subscription_status')
    op.execute('DROP TYPE plan_type') 