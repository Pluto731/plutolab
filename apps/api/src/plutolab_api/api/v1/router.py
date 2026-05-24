"""Aggregate v1 API routes."""

from fastapi import APIRouter

from plutolab_api.api.v1 import db_health, health

api_router = APIRouter()
api_router.include_router(health.router, tags=["health"])
api_router.include_router(db_health.router, tags=["health"])
