"""Generate the native JSON Schemas from the Pydantic models, which are the canonical definition.

Run ``python -m omniuart.schema_export`` to rewrite ``schemas/protocol.schema.json`` and
``schemas/script.schema.json``. A test fails if the committed files differ from the generated ones.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Type

from pydantic import BaseModel

from omniuart.core.models import ProtocolSpec, ScriptSpec

SCHEMA_DIALECT = "https://json-schema.org/draft/2020-12/schema"


def build_schema(model: Type[BaseModel], title: str) -> Dict[str, Any]:
    """JSON Schema (draft 2020-12) of ``model`` as it validates input."""
    schema = model.model_json_schema(mode="validation")
    return {"$schema": SCHEMA_DIALECT, **schema, "title": title}


def build_protocol_schema() -> Dict[str, Any]:
    return build_schema(ProtocolSpec, "OmniUART Protocol Specification Schema")


def build_script_schema() -> Dict[str, Any]:
    return build_schema(ScriptSpec, "OmniUART Automation Script Schema")


def render(schema: Dict[str, Any]) -> str:
    return json.dumps(schema, indent=2) + "\n"


def default_schema_dir() -> Path:
    return Path(__file__).resolve().parents[2] / "schemas"


def main() -> int:
    out = default_schema_dir()
    (out / "protocol.schema.json").write_text(render(build_protocol_schema()), encoding="utf-8")
    (out / "script.schema.json").write_text(render(build_script_schema()), encoding="utf-8")
    print(f"Wrote protocol.schema.json and script.schema.json to {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
