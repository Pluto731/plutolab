"""Aggregate v1 API routes."""

from fastapi import APIRouter

from plutolab_api.api.v1 import health

api_router = APIRouter()
api_router.include_router(health.router, tags=["health"])
