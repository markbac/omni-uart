"""Dynamic Web UI Application Entry Point for OmniUART with Security Hardening."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from omniuart.ui.routes import connection, router

logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(_: FastAPI):
    """Close the serial link when the server stops."""
    yield
    await connection.disconnect()


app = FastAPI(title="OmniUART Dynamic Web UI", version="2.0.0", lifespan=lifespan)

# Restrict CORS to local web browser clients to prevent unauthorized cross-origin requests
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://127.0.0.1:8000", "http://localhost:8000"],
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)

app.include_router(router)
