"""Dynamic Web UI Application Entry Point for OmniUART with Security Hardening."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from omniuart.ui.routes import connection, router
from omniuart.ui.security import LOOPBACK_ORIGIN_REGEX, LocalOnlyMiddleware

logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(_: FastAPI):
    """Close the serial link when the server stops."""
    yield
    await connection.disconnect()


app = FastAPI(title="OmniUART Dynamic Web UI", version="2.0.0", lifespan=lifespan)

# CORS for loopback origins on any port (the UI is served from the same origin, so this is only
# for local tools); LocalOnlyMiddleware additionally guards Host and Origin, including WebSockets.
app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=LOOPBACK_ORIGIN_REGEX,
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)
app.add_middleware(LocalOnlyMiddleware)

app.include_router(router)
