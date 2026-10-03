"""Automated Protocol Fuzzer & MCU Stress Tester for OmniUART.

Every vector is built with the protocol's :class:`FrameCodec` and its outcome is classified from what
the device actually did. A device has no way to say "rejected" other than staying silent (the schema
defines no error frames), so silence on an invalid request is the correct behaviour, silence on a
valid request is a failure, and a liveness probe after each vector detects a device that locked up.
"""

from __future__ import annotations

import asyncio
import logging
import random
from itertools import zip_longest
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

from pydantic import BaseModel, Field

from omniuart.core.limits import get_limits
from omniuart.core.codec import CodecError, FrameCodec, default_value, encode_value
from omniuart.core.session import read_available
from omniuart.core.models import CommandSpec, FieldSpec, FieldType, ProtocolSpec
from omniuart.core.transport import AsyncTransport

logger = logging.getLogger(__name__)

_INTEGER_LIMITS = {
    FieldType.UINT8: (0, 0xFF),
    FieldType.UINT16: (0, 0xFFFF),
    FieldType.UINT32: (0, 0xFFFFFFFF),
    FieldType.UINT64: (0, 0xFFFFFFFFFFFFFFFF),
    FieldType.INT8: (-0x80, 0x7F),
    FieldType.INT16: (-0x8000, 0x7FFF),
    FieldType.INT32: (-0x80000000, 0x7FFFFFFF),
    FieldType.INT64: (-(1 << 63), (1 << 63) - 1),
    FieldType.ENUM: (0, 0xFF),
}


class FuzzOutcome(str, Enum):
    """Classification of what the device did with one fuzz vector."""

    ACCEPTED = "ACCEPTED"  # valid request answered with a valid response (or legitimately silent)
    CORRECTLY_REJECTED = "CORRECTLY_REJECTED"  # invalid request ignored, device still alive
    UNEXPECTEDLY_ACCEPTED = "UNEXPECTEDLY_ACCEPTED"  # invalid request answered as if it were valid
    MALFORMED_RESPONSE = "MALFORMED_RESPONSE"  # device sent bytes that do not decode as a valid response
    TIMEOUT = "TIMEOUT"  # valid request got no response
    HANG = "HANG"  # device stopped answering a valid probe after this vector
    TRANSPORT_ERROR = "TRANSPORT_ERROR"  # the transport raised while writing or reading


_HANDLED = {FuzzOutcome.ACCEPTED, FuzzOutcome.CORRECTLY_REJECTED}


class FuzzVector(BaseModel):
    """Mutated input test vector."""

    strategy: str  # "valid", "out_of_bounds", "corrupted_integrity", "truncated_frame", "random_mutation"
    command_name: str
    params: Dict[str, Any]
    raw_payload: bytes
    expected_failure: bool = True


class FuzzResult(BaseModel):
    """Execution result for a single fuzz vector."""

    vector: FuzzVector
    status: FuzzOutcome
    response_bytes: bytes
    latency_ms: float
    detail: str = ""


class FuzzReport(BaseModel):
    """Summary report of a protocol fuzzing campaign."""

    protocol_name: str
    seed: Optional[int] = None
    total_vectors: int
    outcomes: Dict[str, int] = Field(default_factory=dict)
    results: List[FuzzResult] = Field(default_factory=list)

    def _count(self, *outcomes: FuzzOutcome) -> int:
        return sum(self.outcomes.get(o.value, 0) for o in outcomes)

    @property
    def handled_count(self) -> int:
        """Vectors the device dealt with correctly (accepted valid, or correctly rejected invalid)."""
        return self._count(*_HANDLED)

    @property
    def unexpected_count(self) -> int:
        return self._count(FuzzOutcome.UNEXPECTEDLY_ACCEPTED)

    @property
    def malformed_count(self) -> int:
        return self._count(FuzzOutcome.MALFORMED_RESPONSE)

    @property
    def hang_count(self) -> int:
        """Vectors that timed out or left the device unresponsive."""
        return self._count(FuzzOutcome.TIMEOUT, FuzzOutcome.HANG)

    @property
    def crash_count(self) -> int:
        """Vectors during which the transport itself failed."""
        return self._count(FuzzOutcome.TRANSPORT_ERROR)

    @property
    def passed(self) -> bool:
        """True only when every vector was handled correctly."""
        return self.total_vectors > 0 and self.handled_count == self.total_vectors


class ProtocolFuzzer:
    """Generates protocol boundary fuzzing test vectors and runs them against a transport."""

    def __init__(self, spec: ProtocolSpec, seed: Optional[int] = None) -> None:
        self.spec = spec
        self.codec = FrameCodec(spec)
        self.seed = seed
        self._rng = random.Random(seed)

    # ------------------------------------------------------------------ vector generation
    def _frame(self, cmd: CommandSpec, values: Dict[str, Any], relaxed: Tuple[str, ...] = ()) -> bytes:
        """Encode ``cmd`` with ``values``; fields named in ``relaxed`` skip range and option checks."""
        if not self.codec.is_binary:
            return self.codec.encode_message(cmd.id, b"", params=[str(values[p.name]) for p in cmd.parameters])
        payload = bytearray()
        for spec in cmd.parameters:
            if spec.name in relaxed:
                spec = spec.model_copy(update={"min": None, "max": None, "options": None})
            payload.extend(encode_value(spec, values[spec.name]))
        return self.codec.encode_message(cmd.id, bytes(payload))

    @staticmethod
    def _out_of_range(spec: FieldSpec) -> Optional[Any]:
        """A value just outside the declared bounds that still fits the wire type, if one exists."""
        if spec.type in _INTEGER_LIMITS:
            low, high = _INTEGER_LIMITS[spec.type]
            if spec.max is not None and spec.max + 1 <= high:
                return int(spec.max) + 1
            if spec.min is not None and spec.min - 1 >= low:
                return int(spec.min) - 1
            if spec.type is FieldType.ENUM and spec.options:
                unused = [v for v in range(low, high + 1) if str(v) not in {str(k) for k in spec.options}]
                return unused[0] if unused else None
            return None
        if spec.type in (FieldType.FLOAT32, FieldType.FLOAT64):
            if spec.max is not None:
                return spec.max + 1.0
            if spec.min is not None:
                return spec.min - 1.0
        return None

    def generate_vectors_for_command(self, cmd: CommandSpec) -> List[FuzzVector]:
        """Build a valid baseline plus mutated vectors for ``cmd``. Strategies that do not apply are omitted."""
        values = {p.name: default_value(p) for p in cmd.parameters}
        try:
            valid = self._frame(cmd, values)
        except CodecError as exc:
            logger.warning("Skipping command '%s': cannot build a valid frame (%s)", cmd.name, exc)
            return []

        vectors = [FuzzVector(strategy="valid", command_name=cmd.name, params=values, raw_payload=valid, expected_failure=False)]

        # Out-of-bounds: push one bounded parameter just past its declared limit.
        for spec in cmd.parameters:
            bad = self._out_of_range(spec)
            if bad is None:
                continue
            oob = {**values, spec.name: bad}
            try:
                raw = self._frame(cmd, oob, relaxed=(spec.name,))
            except CodecError:
                continue
            vectors.append(FuzzVector(strategy="out_of_bounds", command_name=cmd.name, params=oob, raw_payload=raw))
            break

        # Corrupted integrity field (only when the protocol has one).
        width = self.codec.integrity_size
        if width:
            tail = len(self.codec.footer_bytes)
            index = len(valid) - tail - 1  # last byte of the integrity field
            corrupted = bytearray(valid)
            corrupted[index] ^= 0xFF
            vectors.append(FuzzVector(strategy="corrupted_integrity", command_name=cmd.name, params=values, raw_payload=bytes(corrupted)))

        # Truncated frame: the device must wait for the rest, then give up.
        if len(valid) > 1:
            vectors.append(FuzzVector(strategy="truncated_frame", command_name=cmd.name, params=values, raw_payload=valid[: max(1, len(valid) // 2)]))

        # Random single-byte mutation; it only counts as a failure if the result is no longer a valid frame.
        mutated = bytearray(valid)
        mutated[self._rng.randrange(len(mutated))] ^= self._rng.randint(1, 255)
        still_valid = self.codec.decode(bytes(mutated), direction="request").ok
        vectors.append(
            FuzzVector(strategy="random_mutation", command_name=cmd.name, params=values, raw_payload=bytes(mutated), expected_failure=not still_valid)
        )
        return vectors

    def select_vectors(self, max_vectors: int) -> List[FuzzVector]:
        """Up to ``max_vectors`` vectors spread across every command.

        Vectors are interleaved round-robin (each command's valid baseline first, then its mutations)
        so a small budget still touches every command instead of exhausting the first few.
        """
        per_command = [self.generate_vectors_for_command(cmd) for cmd in self.spec.commands]
        interleaved = [v for group in zip_longest(*per_command) for v in group if v is not None]
        return interleaved[: min(max_vectors, get_limits().fuzz_vectors)]

    # ------------------------------------------------------------------ execution
    def _probe(self) -> Optional[Tuple[CommandSpec, bytes]]:
        """A valid request the device must always answer, used to detect lock-ups."""
        for cmd in self.spec.commands:
            if cmd.response is None:
                continue
            try:
                return cmd, self._frame(cmd, {p.name: default_value(p) for p in cmd.parameters})
            except CodecError:
                continue
        return None

    def _is_valid_response(self, data: bytes) -> bool:
        frames, rest = self.codec.extract_frames(data, direction="response")
        return bool(frames) and not rest and all(f.ok for f in frames)

    async def _run_vector(self, transport: AsyncTransport, vec: FuzzVector, timeout_ms: int, probe: Optional[Tuple[CommandSpec, bytes]]) -> FuzzResult:
        loop = asyncio.get_running_loop()
        start = loop.time()
        cmd = self.spec.get_command(vec.command_name)
        expects_response = cmd is not None and cmd.response is not None
        try:
            await transport.write(vec.raw_payload)
            resp = await read_available(transport, timeout_ms)
        except Exception as exc:  # noqa: BLE001 - any transport failure is a result, not a crash of the campaign
            return FuzzResult(vector=vec, status=FuzzOutcome.TRANSPORT_ERROR, response_bytes=b"", latency_ms=0.0, detail=f"{type(exc).__name__}: {exc}")
        latency = (loop.time() - start) * 1000.0

        if resp and not self._is_valid_response(resp):
            return FuzzResult(vector=vec, status=FuzzOutcome.MALFORMED_RESPONSE, response_bytes=resp, latency_ms=latency, detail="response bytes do not decode")
        if resp and vec.expected_failure:
            return FuzzResult(vector=vec, status=FuzzOutcome.UNEXPECTEDLY_ACCEPTED, response_bytes=resp, latency_ms=latency, detail="invalid request was answered")
        if not resp and not vec.expected_failure and expects_response:
            return FuzzResult(vector=vec, status=FuzzOutcome.TIMEOUT, response_bytes=b"", latency_ms=latency, detail="valid request got no response")

        status = FuzzOutcome.CORRECTLY_REJECTED if vec.expected_failure else FuzzOutcome.ACCEPTED
        if vec.expected_failure and probe is not None:
            probe_cmd, probe_frame = probe
            try:
                await transport.write(probe_frame)
                alive = await read_available(transport, timeout_ms)
            except Exception as exc:  # noqa: BLE001
                return FuzzResult(vector=vec, status=FuzzOutcome.TRANSPORT_ERROR, response_bytes=resp, latency_ms=latency, detail=f"probe failed: {exc}")
            if not self._is_valid_response(alive):
                return FuzzResult(vector=vec, status=FuzzOutcome.HANG, response_bytes=alive, latency_ms=latency, detail=f"device did not answer '{probe_cmd.name}' afterwards")
        return FuzzResult(vector=vec, status=status, response_bytes=resp, latency_ms=latency)

    async def run_campaign(self, transport: AsyncTransport, max_vectors: int = 50, timeout_ms: int = 200) -> FuzzReport:
        """Run the campaign and return a report whose outcome counts add up to ``total_vectors``."""
        if not transport.is_open:
            await transport.open()

        vectors = self.select_vectors(max_vectors)

        probe = self._probe()
        results = [await self._run_vector(transport, vec, timeout_ms, probe) for vec in vectors]
        outcomes: Dict[str, int] = {}
        for result in results:
            outcomes[result.status.value] = outcomes.get(result.status.value, 0) + 1
        return FuzzReport(protocol_name=self.spec.metadata.name, seed=self.seed, total_vectors=len(results), outcomes=outcomes, results=results)
