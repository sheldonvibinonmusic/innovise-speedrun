"""Aggregated API Routers Package.

Combines sub-routers for health, runs, documents, company discovery, reports, and retrieval.
"""

from fastapi import APIRouter

from app.api.routes.company import router as company_router
from app.api.routes.documents import router as documents_router
from app.api.routes.health import router as health_router
from app.api.routes.reports import router as reports_router
from app.api.routes.retrieval import router as retrieval_router
from app.api.routes.runs import router as runs_router

api_router = APIRouter(prefix="/api")
api_router.include_router(health_router)
api_router.include_router(runs_router)
api_router.include_router(documents_router)
api_router.include_router(company_router)
api_router.include_router(reports_router)
api_router.include_router(retrieval_router)

__all__ = ["api_router"]
