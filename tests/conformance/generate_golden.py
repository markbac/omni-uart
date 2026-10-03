"""Regenerate ``golden/vectors.json``: ``PYTHONPATH=. python -m tests.conformance.generate_golden``."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict

from omniuart.core.codec import FrameCodec
from tests.conformance.support import KNOWN_GAPS, command_cases, encode_request, sample_params

GOLDEN = Path(__file__).parent / "golden" / "vectors.json"


def jsonable(value: Any) -> Any:
    if isinstance(value, (bytes, bytearray)):
        return bytes(value).hex(" ").upper()
    if isinstance(value, dict):
        return {str(k): jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [jsonable(v) for v in value]
    return value


def build() -> Dict[str, Any]:
    vectors: Dict[str, Any] = {}
    for name, spec, cmd in command_cases():
        if (name, cmd.name) in KNOWN_GAPS:
            continue
        codec = FrameCodec(spec)
        raw = encode_request(spec, cmd)
        entry: Dict[str, Any] = {
            "params": jsonable(sample_params(cmd)),
            "request": raw.hex(" ").upper(),
            "decoded": jsonable(codec.decode(raw, direction="request").fields),
        }
        if cmd.response is not None:
            try:
                resp = codec.encode_response(cmd)
            except Exception:  # noqa: BLE001 - a response that cannot be built from defaults has no golden vector
                resp = None
            if resp is not None:
                entry["response"] = resp.hex(" ").upper()
        vectors.setdefault(name, {})[cmd.name] = entry
    return vectors


if __name__ == "__main__":
    GOLDEN.parent.mkdir(exist_ok=True)
    GOLDEN.write_text(json.dumps(build(), indent=1, sort_keys=True) + "\n", encoding="utf-8")
    print(f"wrote {GOLDEN}")
