from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.trustedhost import TrustedHostMiddleware

from .api.routes import aws, conversations, findings, health, mcp, settings
from .config import get_settings
from .db import close_database, initialize_database

app_settings = get_settings()


@asynccontextmanager
async def lifespan(_app: FastAPI):
    await initialize_database()
    yield
    await close_database()


app = FastAPI(
    title="OpsLens API",
    version="0.1.0",
    description="Local read-only AWS operations API",
    lifespan=lifespan,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[app_settings.frontend_origin],
    allow_credentials=False,
    allow_methods=["GET", "POST", "PUT"],
    allow_headers=["Content-Type", "X-OpsLens-Session"],
)
app.add_middleware(TrustedHostMiddleware, allowed_hosts=["127.0.0.1", "localhost"])

app.include_router(health.router, prefix="/api/v1")
app.include_router(settings.router, prefix="/api/v1")
app.include_router(aws.router, prefix="/api/v1")
app.include_router(findings.router, prefix="/api/v1")
app.include_router(mcp.router, prefix="/api/v1")
app.include_router(conversations.router, prefix="/api/v1")


@app.get("/")
async def root() -> dict[str, str]:
    return {
        "application": "OpsLens",
        "message": "Local API is running. Open the React application on 127.0.0.1:5173.",
        "docs": "/docs",
    }
