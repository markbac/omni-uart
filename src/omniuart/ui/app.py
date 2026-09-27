"""Dynamic Web UI Application Entry Point for OmniUART with Security Hardening."""

from __future__ import annotations

import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from omniuart.ui.routes import router

logger = logging.getLogger(__name__)

app = FastAPI(title="OmniUART Dynamic Web UI", version="2.0.0")

# Restrict CORS to local web browser clients to prevent unauthorized cross-origin requests
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://127.0.0.1:8000", "http://localhost:8000"],
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)

app.include_router(router)
