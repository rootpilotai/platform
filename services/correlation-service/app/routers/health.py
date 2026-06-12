import logging

from fastapi import APIRouter, Depends

from app.config import CorrelationServiceSettings
from app.dependencies import get_settings

logger = logging.getLogger(__name__)

router = APIRouter(tags=["health"])


@router.get("/health")
async def health(settings: CorrelationServiceSettings = Depends(get_settings)) -> dict:
    return {
        "status": "healthy",
        "service": settings.service_name,
        "environment": settings.environment,
    }
