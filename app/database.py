from sqlmodel import SQLModel, create_engine, Session
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy import text
from .config import settings
import logging
import ssl

logger = logging.getLogger(__name__)

# Configurar SSL para Neon
ssl_context = ssl.create_default_context()
ssl_context.check_hostname = False
ssl_context.verify_mode = ssl.CERT_NONE

# Convert DATABASE_URL to use asyncpg driver
async_database_url = settings.DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://")

# Create async engine for FastAPI with SSL configuration
engine = create_async_engine(
    async_database_url,
    echo=settings.ENVIRONMENT == "development",
    future=True,
    pool_pre_ping=True,
    pool_size=5,
    max_overflow=10,
    connect_args={
        "ssl": ssl_context,
        "server_settings": {
            "application_name": "opina_app",
        },
    }
)

# Create async session maker
async_session_maker = sessionmaker(
    engine, 
    class_=AsyncSession, 
    expire_on_commit=False
)

async def get_db():
    """
    Dependency to get database session
    """
    async with async_session_maker() as session:
        yield session

async def init_db():
    """
    Verifica a conexão com o banco de dados
    """
    try:
        async with engine.connect() as conn:
            result = await conn.execute(text("SELECT 1"))
            row = result.fetchone()
            await conn.commit()
        logger.info("Database connection verified successfully")
    except Exception as e:
        logger.error(f"Failed to connect to database: {e}")
        raise

async def get_session() -> AsyncSession:
    """
    Dependency para injetar sessões do banco
    """
    async with async_session_maker() as session:
        try:
            yield session
        finally:
            await session.close()

# Função para resetar o banco (usar apenas em desenvolvimento)
async def reset_db():
    """
    Recria todas as tabelas (CUIDADO: apaga todos os dados)
    """
    try:
        async with engine.begin() as conn:
            await conn.run_sync(SQLModel.metadata.drop_all)
            await conn.run_sync(SQLModel.metadata.create_all)
            logger.info("Database reset successfully")
    except Exception as e:
        logger.error(f"Error resetting database: {e}")
        raise 