"""Dynamic Web UI Application Entry Point for OmniUART."""

from __future__ import annotations

import logging
from fastapi import FastAPI
from omniuart.ui.routes import router

logger = logging.getLogger(__name__)

app = FastAPI(title="OmniUART Dynamic Web UI", version="2.0.0")
app.include_router(router)
