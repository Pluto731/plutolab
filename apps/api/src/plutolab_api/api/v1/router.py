"""Aggregate v1 API routes."""

from fastapi import APIRouter

from plutolab_api.api.v1 import (
    agent_runs,
    agents,
    api_keys,
    auth,
    dashboard,
    db_health,
    health,
    links,
    notes,
    pomodoros,
    rag,
    review,
    tasks,
    users,
    workflows,
)

api_router = APIRouter()
api_router.include_router(health.router, tags=["health"])
api_router.include_router(db_health.router, tags=["health"])
api_router.include_router(auth.router)
api_router.include_router(users.router)
api_router.include_router(dashboard.router)
api_router.include_router(api_keys.router)
api_router.include_router(notes.router)
api_router.include_router(tasks.router)
api_router.include_router(links.router)
api_router.include_router(pomodoros.router)
api_router.include_router(rag.router)
api_router.include_router(review.router)
api_router.include_router(agents.router)
api_router.include_router(workflows.router)
api_router.include_router(agent_runs.router)
