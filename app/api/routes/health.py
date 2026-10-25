"""System Health and Readiness Route.

Endpoint: GET /api/health
"""

from fastapi import APIRouter, Depends, status
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.config import settings
from app.db.session import get_db
from app.schemas.common import HealthResponse

router = APIRouter(tags=["Health"])


@router.get(
    "/health",
    response_model=HealthResponse,
    summary="Check system and database health",
    description="Returns backend service status, database connectivity, and configuration flags.",
)
def get_health(db: Session = Depends(get_db)):
    """Evaluate database connectivity and operational readiness."""
    database_connected = False
    try:
        # Probe SQLite connectivity with a trivial query
        result = db.execute(text("SELECT 1")).scalar()
        if result == 1:
            database_connected = True
    except Exception:
        database_connected = False

    overall_status = "healthy" if database_connected else "degraded"
    status_code = status.HTTP_200_OK if database_connected else status.HTTP_503_SERVICE_UNAVAILABLE

    qdrant_available = False
    try:
        from app.retrieval.service import retrieval_service
        qdrant_available = retrieval_service.vector_store is not None
    except Exception:
        qdrant_available = settings.qdrant_path.exists()

    optional_components = {
        "llm_api_key_configured": bool(settings.llm_api_key and settings.llm_api_key != "your_api_key_here"),
        "upload_dir_ready": settings.upload_dir.exists(),
        "qdrant_ready": qdrant_available,
        "qdrant_dir_ready": settings.qdrant_path.exists(),
    }

    response_data = HealthResponse(
        status=overall_status,
        version=settings.app_version,
        environment=settings.app_env,
        database_connected=database_connected,
        optional_components=optional_components,
    )

    if not database_connected:
        return JSONResponse(status_code=status_code, content=response_data.model_dump())

    return response_data
