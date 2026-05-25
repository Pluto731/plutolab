"""PlutoLab FastAPI app entry."""

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text

from plutolab_api.api.v1.router import api_router
from plutolab_api.core.config import settings
from plutolab_api.core.logging import configure_logging, get_logger
from plutolab_api.db.session import dispose_engine, engine

configure_logging(level=settings.log_level)
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(_: FastAPI):
    logger.info("plutolab.api.startup", version=settings.version, env=settings.env)
    # Smoke-test DB connection so we fail fast on startup, not on the first request.
    async with engine.begin() as conn:
        await conn.execute(text("SELECT 1"))
    logger.info("plutolab.api.db_connected", url=settings.database_url.split("@")[-1])
    # 确保头像目录存在 (StaticFiles 挂载要求目录已存在)
    Path(settings.avatar_dir).mkdir(parents=True, exist_ok=True)
    yield
    await dispose_engine()
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

# 头像静态文件 (check_dir=False: 目录由 lifespan startup 创建)
app.mount(
    "/api/v1/avatars",
    StaticFiles(directory=settings.avatar_dir, check_dir=False),
    name="avatars",
)
