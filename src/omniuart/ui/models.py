"""UI Request & Response Models for FastAPI Endpoints."""

from __future__ import annotations

from typing import Any, Dict
from pydantic import BaseModel


class CommandRequest(BaseModel):
    """Payload model for sending protocol command."""
    command: str
    params: Dict[str, Any] = {}


class SerialConnectRequest(BaseModel):
    """Payload model for establishing serial port connection."""
    port: str
    baudrate: int = 115200
    rts: bool = True
    dtr: bool = True
