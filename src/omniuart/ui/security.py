"""Request guards for the local web UI: loopback-only Host and Origin checks.

The UI controls real hardware, so it must not be reachable through a web page the user happens to visit
(CORS does not apply to WebSockets) or through DNS rebinding (a hostile name that resolves to 127.0.0.1).
"""

from __future__ import annotations

import ipaddress
from typing import Iterable, Optional
from urllib.parse import urlsplit

from starlette.responses import PlainTextResponse
from starlette.types import ASGIApp, Receive, Scope, Send

# ``testserver`` is the Host header Starlette's TestClient sends.
DEFAULT_ALLOWED_HOSTS = ("localhost", "127.0.0.1", "::1", "testserver")
LOOPBACK_ORIGIN_REGEX = r"^https?://(127\.0\.0\.1|localhost|\[::1\])(:\d+)?$"


def is_loopback_host(host: Optional[str]) -> bool:
    """Whether ``host`` is ``localhost`` or a loopback IP address."""
    if not host:
        return False
    if host.lower() == "localhost":
        return True
    try:
        return ipaddress.ip_address(host.strip("[]")).is_loopback
    except ValueError:
        return False


def _hostname(value: str, *, is_origin: bool) -> Optional[str]:
    try:
        return urlsplit(value if is_origin else f"//{value}").hostname
    except ValueError:
        return None


class LocalOnlyMiddleware:
    """Reject requests (HTTP and WebSocket) whose ``Host`` or ``Origin`` is not a permitted local name.

    A request without an ``Origin`` header (curl, scripts, the desktop app) is allowed; browsers always
    send one on WebSocket upgrades and cross-site writes, which is what this stops.
    """

    def __init__(self, app: ASGIApp, allowed_hosts: Iterable[str] = DEFAULT_ALLOWED_HOSTS) -> None:
        self.app = app
        self.allowed = {h.lower() for h in allowed_hosts}

    def _permitted(self, scope: Scope) -> bool:
        headers = {k.decode("latin-1").lower(): v.decode("latin-1") for k, v in scope.get("headers", [])}
        host = _hostname(headers.get("host", ""), is_origin=False)
        if host is None or host.lower() not in self.allowed:
            return False
        origin = headers.get("origin")
        if origin is not None:
            origin_host = _hostname(origin, is_origin=True)
            if origin_host is None or origin_host.lower() not in self.allowed:
                return False
        return True

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] in ("http", "websocket") and not self._permitted(scope):
            if scope["type"] == "websocket":
                await receive()  # consume websocket.connect, then refuse the upgrade
                await send({"type": "websocket.close", "code": 1008})
            else:
                await PlainTextResponse("Forbidden: host or origin not allowed", status_code=403)(scope, receive, send)
            return
        await self.app(scope, receive, send)
