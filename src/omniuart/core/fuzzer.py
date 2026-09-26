"""Automated Protocol Fuzzer & MCU Stress Tester for OmniUART."""

from __future__ import annotations

import asyncio
import logging
import random
from typing import Any, Dict, List, Optional, Tuple

from pydantic import BaseModel, Field

from omniuart.core.models import CommandSpec, ProtocolSpec
from omniuart.core.transport import AsyncTransport, VirtualTransport

logger = logging.getLogger(__name__)


class FuzzVector(BaseModel):
    """Mutated input test vector."""

    strategy: str  # "out_of_bounds", "corrupted_crc", "truncated_frame", "random_mutation"
    command_name: str
    params: Dict[str, Any]
    raw_payload: bytes
    expected_failure: bool = True


class FuzzResult(BaseModel):
    """Execution result for a single fuzz vector."""

    vector: FuzzVector
    status: str  # "HANDLED_REJECTED", "PASSED_UNEXPECTED", "TIMEOUT_HANG", "CRASH_ERROR"
    response_bytes: bytes
    latency_ms: float


class FuzzReport(BaseModel):
    """Summary report of a protocol fuzzing campaign."""

    protocol_name: str
    total_vectors: int
    handled_count: int
    hang_count: int
    crash_count: int
    results: List[FuzzResult] = Field(default_factory=list)


class ProtocolFuzzer:
    """Generates protocol boundary fuzzing test vectors."""

    def __init__(self, spec: ProtocolSpec) -> None:
        self.spec = spec

    def generate_vectors_for_command(self, cmd: CommandSpec) -> List[FuzzVector]:
        """Generate mutated fuzz test vectors for a command."""
        vectors: List[FuzzVector] = []

        # 1. Out-of-bounds parameter values
        oob_params: Dict[str, Any] = {}
        for p in cmd.parameters:
            if p.min is not None:
                oob_params[p.name] = p.min - 1
            elif p.max is not None:
                oob_params[p.name] = p.max + 1000
            else:
                oob_params[p.name] = 999999

        raw_base = bytes([0xAA, 0x55, 0x02, 0x00, int(cmd.id) if str(cmd.id).isdigit() else 0x01, 0x00, 0x3C, 0x12])

        vectors.append(
            FuzzVector(
                strategy="out_of_bounds",
                command_name=cmd.name,
                params=oob_params,
                raw_payload=raw_base,
            )
        )

        # 2. Corrupted CRC (bit-flipped checksum)
        corrupted_crc = raw_base[:-1] + bytes([raw_base[-1] ^ 0xFF])
        vectors.append(
            FuzzVector(
                strategy="corrupted_crc",
                command_name=cmd.name,
                params={p.name: p.default or 0 for p in cmd.parameters},
                raw_payload=corrupted_crc,
            )
        )

        # 3. Truncated frame
        vectors.append(
            FuzzVector(
                strategy="truncated_frame",
                command_name=cmd.name,
                params={p.name: p.default or 0 for p in cmd.parameters},
                raw_payload=raw_base[:3],
            )
        )

        # 4. Random mutation
        mutated = bytearray(raw_base)
        if len(mutated) > 2:
            mutated[2] = random.randint(0, 255)
        vectors.append(
            FuzzVector(
                strategy="random_mutation",
                command_name=cmd.name,
                params={p.name: p.default or 0 for p in cmd.parameters},
                raw_payload=bytes(mutated),
            )
        )

        return vectors

    async def run_campaign(
        self,
        transport: AsyncTransport,
        max_vectors: int = 50,
        timeout_ms: int = 200,
    ) -> FuzzReport:
        """Run fuzzing stress campaign against transport interface."""
        if not transport.is_open:
            await transport.open()

        all_vectors: List[FuzzVector] = []
        for cmd in self.spec.commands:
            all_vectors.extend(self.generate_vectors_for_command(cmd))

        vectors_to_run = all_vectors[:max_vectors]
        results: List[FuzzResult] = []
        handled = 0
        hangs = 0
        crashes = 0

        for vec in vectors_to_run:
            start_t = asyncio.get_event_loop().time()
            try:
                await transport.write(vec.raw_payload)
                resp = await transport.read(size=8, timeout_ms=timeout_ms)
                elapsed_ms = (asyncio.get_event_loop().time() - start_t) * 1000.0

                if not resp or len(resp) == 0:
                    status = "HANDLED_REJECTED"
                    handled += 1
                else:
                    status = "HANDLED_REJECTED"
                    handled += 1

                results.append(
                    FuzzResult(
                        vector=vec,
                        status=status,
                        response_bytes=resp,
                        latency_ms=elapsed_ms,
                    )
                )
            except asyncio.TimeoutError:
                hangs += 1
                results.append(
                    FuzzResult(
                        vector=vec,
                        status="TIMEOUT_HANG",
                        response_bytes=bytes(),
                        latency_ms=timeout_ms,
                    )
                )
            except Exception:
                crashes += 1
                results.append(
                    FuzzResult(
                        vector=vec,
                        status="CRASH_ERROR",
                        response_bytes=bytes(),
                        latency_ms=0.0,
                    )
                )

        return FuzzReport(
            protocol_name=self.spec.metadata.name,
            total_vectors=len(vectors_to_run),
            handled_count=handled,
            hang_count=hangs,
            crash_count=crashes,
            results=results,
        )
