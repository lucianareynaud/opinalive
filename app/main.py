from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import logging
import uvicorn
import os

from .routes import feedback, auth, webhooks, payments, health, dashboard, web, company
from .database import init_db
from .config import settings

# Configuração de logging
logging.basicConfig(level=settings.LOG_LEVEL)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Opina API",
    description="API para processamento e análise de feedback via áudio.",
    version="1.0.0"
)

# Configuração de CORS baseada no ambiente
cors_origins = ["*"] if settings.ENVIRONMENT == "development" else settings.CORS_ORIGINS

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Montar arquivos estáticos (CSS, JS, imagens)
if os.path.exists("app/static"):
    app.mount("/static", StaticFiles(directory="app/static"), name="static")

@app.get("/api")
async def api_info():
    """
    Rota que retorna informações básicas sobre a API
    """
    return {
        "name": "Opina API",
        "version": "1.0.0",
        "description": "API para processamento e análise de feedback via áudio",
        "documentation": "/docs",
        "endpoints": {
            "feedback": "/feedback",
            "auth": "/auth",
            "webhooks": "/webhooks"
        }
    }

# Monta rotas da aplicação (ordem importa - mais específicas primeiro)
app.include_router(health.router, prefix="/health", tags=["health"])
app.include_router(feedback.router, prefix="/feedback", tags=["feedback"])
app.include_router(auth.router, prefix="/auth", tags=["auth"])
app.include_router(webhooks.router, prefix="/webhooks", tags=["webhooks"])
app.include_router(payments.router, prefix="/payments", tags=["payments"])
app.include_router(company.router, prefix="/company", tags=["company"])
app.include_router(web.router, tags=["web"])
app.include_router(dashboard.router, tags=["dashboard"])  # Deve ser o último para pegar rotas como "/"

@app.on_event("startup")
async def startup_event():
    """
    Inicializa recursos na startup
    """
    logger.info("Initializing application...")
    await init_db()
    logger.info("Application startup complete")

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    uvicorn.run(app, host="0.0.0.0", port=port)
