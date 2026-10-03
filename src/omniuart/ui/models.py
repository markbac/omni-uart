"""UI Request & Response Models for FastAPI Endpoints."""

from __future__ import annotations

from typing import Any, Dict, Optional
from pydantic import BaseModel, Field


class CommandRequest(BaseModel):
    """Payload model for sending protocol command."""
    command: str
    params: Dict[str, Any] = {}


class SerialConnectRequest(BaseModel):
    """Payload model for establishing serial port connection."""
    port: str = Field(min_length=1, description="Serial port name or PySerial URL, or 'virtual' for the labelled simulated device")
    baudrate: int = Field(default=115200, gt=0, le=4_000_000)
    rts: bool = True
    dtr: bool = True
    protocol: Optional[str] = Field(default=None, description="Protocol the simulated device implements (required when port is 'virtual')")
