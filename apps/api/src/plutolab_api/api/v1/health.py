"""Health check endpoint."""

from fastapi import APIRouter
from pydantic import BaseModel

from plutolab_api.core.config import settings

router = APIRouter()


class HealthResponse(BaseModel):
    status: str
    version: str
    env: str


@router.get("/health", response_model=HealthResponse, summary="Health check")
async def health() -> HealthResponse:
    return HealthResponse(status="ok", version=settings.version, env=settings.env)
