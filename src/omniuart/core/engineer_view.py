"""Engineer Raw-Protocol Diagnostic View Subsystem for OmniUART (#234).

Provides detailed engineer diagnostic views alongside operator-friendly UIs, showing decoded messages,
field bit/byte offsets, lengths, hex chunks, CRC/checksum integrity validation, transport latency,
and request/response relationship inspection.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from omniuart.core.dissector import FieldSlice, dissect_frame
from omniuart.core.models import ProtocolSpec
from omniuart.core.session import Exchange


@dataclass
class ProtocolExchangeDetail:
    """Detailed engineer diagnostic inspection of a single request/response exchange (#234)."""

    exchange_id: str
    command_name: str
    timestamp: float
    status: str
    latency_ms: float
    request_raw_hex: str
    response_raw_hex: str
    request_field_slices: List[Dict[str, Any]] = field(default_factory=list)
    response_field_slices: List[Dict[str, Any]] = field(default_factory=list)
    crc_algorithm: str = "none"
    crc_valid: bool = True
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "exchange_id": self.exchange_id,
            "command_name": self.command_name,
            "timestamp": self.timestamp,
            "status": self.status,
            "latency_ms": round(self.latency_ms, 3),
            "request_raw_hex": self.request_raw_hex,
            "response_raw_hex": self.response_raw_hex,
            "request_field_slices": self.request_field_slices,
            "response_field_slices": self.response_field_slices,
            "crc_algorithm": self.crc_algorithm,
            "crc_valid": self.crc_valid,
            "error": self.error,
        }


class EngineerProtocolView:
    """Manager for recording and inspecting raw protocol exchanges in Engineer View."""

    def __init__(self, spec: ProtocolSpec) -> None:
        self.spec = spec
        self.exchanges: Dict[str, ProtocolExchangeDetail] = {}

    def inspect_exchange(self, exchange: Exchange, exchange_id: Optional[str] = None) -> ProtocolExchangeDetail:
        """Inspect and dissect an exchange into detailed engineer representation."""
        ex_id = exchange_id or f"ex_{len(self.exchanges) + 1}_{int(time.time() * 1000)}"

        req_hex = exchange.request.hex(" ").upper() if exchange.request else ""
        resp_hex = exchange.response_bytes.hex(" ").upper() if exchange.response_bytes else ""

        req_slices: List[Dict[str, Any]] = []
        resp_slices: List[Dict[str, Any]] = []

        if exchange.request:
            req_dissected = dissect_frame(self.spec, exchange.request, direction="request")
            req_slices = [
                {
                    "name": s.field_name,
                    "offset": s.start_offset,
                    "length": s.length_bytes,
                    "value": s.decoded_value,
                    "type": s.field_type,
                    "hex_chunk": s.hex_str,
                }
                for s in req_dissected.field_slices
            ]

        if exchange.response_bytes:
            resp_dissected = dissect_frame(self.spec, exchange.response_bytes, direction="response")
            resp_slices = [
                {
                    "name": s.field_name,
                    "offset": s.start_offset,
                    "length": s.length_bytes,
                    "value": s.decoded_value,
                    "type": s.field_type,
                    "hex_chunk": s.hex_str,
                }
                for s in resp_dissected.field_slices
            ]

        crc_alg = self.spec.framing.integrity.algorithm if self.spec.framing.integrity else "none"
        crc_ok = exchange.response.ok if exchange.response else True

        detail = ProtocolExchangeDetail(
            exchange_id=ex_id,
            command_name=exchange.command,
            timestamp=time.time(),
            status=exchange.status.value,
            latency_ms=exchange.latency_ms,
            request_raw_hex=req_hex,
            response_raw_hex=resp_hex,
            request_field_slices=req_slices,
            response_field_slices=resp_slices,
            crc_algorithm=crc_alg,
            crc_valid=crc_ok,
            error=exchange.error,
        )

        self.exchanges[ex_id] = detail
        return detail

    def get_exchange(self, exchange_id: str) -> Optional[ProtocolExchangeDetail]:
        return self.exchanges.get(exchange_id)

    def render_engineer_html_summary(self, exchange_id: str) -> str:
        """Render detailed HTML drill-down view for Engineer UI mode."""
        ex = self.get_exchange(exchange_id)
        if not ex:
            return f"<div>Exchange '{exchange_id}' not found</div>"

        html = f"""
<div class="engineer-detail" style="font-family: monospace; background: #0f172a; color: #f8fafc; padding: 16px; border-radius: 8px;">
  <h3 style="color: #38bdf8; margin-top:0;">🔧 Engineer Raw Protocol Detail - {ex.command_name} ({ex.exchange_id})</h3>
  <div><strong>Status:</strong> {ex.status.upper()} | <strong>Latency:</strong> {ex.latency_ms:.2f} ms | <strong>CRC Alg:</strong> {ex.crc_algorithm}</div>
  <hr style="border-color: #334155;">
  <div><strong>Outbound TX Raw Bytes:</strong> <span style="color: #4ade80;">{ex.request_raw_hex}</span></div>
  <div><strong>Inbound RX Raw Bytes:</strong> <span style="color: #f43f5e;">{ex.response_raw_hex or '(None)'}</span></div>
  <h4 style="color: #cbd5e1; margin-bottom: 8px;">Response Field Dissection:</h4>
  <table style="width: 100%; text-align: left; border-collapse: collapse; font-size: 0.9rem;">
    <tr style="border-bottom: 1px solid #334155; color: #94a3b8;">
      <th>Field Name</th><th>Offset</th><th>Length</th><th>Value</th><th>Hex Chunk</th>
    </tr>
"""
        for fs in ex.response_field_slices:
            html += f"""
    <tr style="border-bottom: 1px solid #1e293b;">
      <td>{fs['name']}</td><td>+{fs['offset']}</td><td>{fs['length']} B</td><td>{fs['value']}</td><td><code>{fs['hex_chunk']}</code></td>
    </tr>
"""
        html += """
  </table>
</div>
"""
        return html
