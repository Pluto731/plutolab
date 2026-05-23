"""PlutoLab FastAPI app entry."""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from plutolab_api.api.v1.router import api_router
from plutolab_api.core.config import settings
from plutolab_api.core.logging import configure_logging, get_logger

configure_logging(level=settings.log_level)
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(_: FastAPI):
    logger.info("plutolab.api.startup", version=settings.version, env=settings.env)
    yield
    logger.info("plutolab.api.shutdown")


app = FastAPI(
    title="PlutoLab API",
    description="PlutoLab — Your AI Workshop, backend service.",
    version=settings.version,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix="/api/v1")
