from fastapi import APIRouter

router = APIRouter()

from . import auth, feedback, webhooks, dashboard, company

# Auth routes (login, logout, Google OAuth)
router.include_router(auth.router, prefix="", tags=["auth"])

# Dashboard routes (páginas principais)
router.include_router(dashboard.router, prefix="", tags=["dashboard"])

# API routes
router.include_router(feedback.router, prefix="/feedback", tags=["feedback"])
router.include_router(webhooks.router, prefix="/webhooks", tags=["webhooks"])
router.include_router(company.router) 