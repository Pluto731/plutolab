"""Aggregate v1 API routes."""

from fastapi import APIRouter

from plutolab_api.api.v1 import api_keys, auth, dashboard, db_health, health, users

api_router = APIRouter()
api_router.include_router(health.router, tags=["health"])
api_router.include_router(db_health.router, tags=["health"])
api_router.include_router(auth.router)
api_router.include_router(users.router)
api_router.include_router(dashboard.router)
api_router.include_router(api_keys.router)
