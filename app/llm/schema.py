"""Pydantic-to-OpenAI-strict-JSON-schema adapter.

OpenAI's structured-outputs API (``response_format={"type": "json_schema",
"strict": True, ...}``) enforces the schema at the provider, eliminating
LLM compliance drift on prompt-only constraints. This module derives a
strict schema from any Pydantic v2 model that uses ``extra="forbid"`` on
every nested model.

Strict-mode rules enforced here:

- Every object has ``additionalProperties: false``.
- Every property is in ``required``. Optional fields are union'd with null.
- ``$defs`` references kept intact (OpenAI strict mode supports them).
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel


def strict_schema_for(model: type[BaseModel], *, name: str | None = None) -> dict[str, Any]:
    """Return an OpenAI ``response_format`` payload for ``model``."""
    raw = model.model_json_schema()
    schema = _walk(raw)
    return {
        "type": "json_schema",
        "json_schema": {
            "name": name or model.__name__,
            "schema": schema,
            "strict": True,
        },
    }


_STRIPPED_KEYS = frozenset({"default", "title", "examples"})


def _walk(node: Any) -> Any:
    """Recursively rewrite a Pydantic JSON schema into OpenAI strict form."""
    if isinstance(node, dict):
        out: dict[str, Any] = {}
        for key, value in node.items():
            if key in _STRIPPED_KEYS:
                # Strict mode rejects ``default``. ``title`` and ``examples`` are
                # cosmetic; drop them to keep the payload small.
                continue
            out[key] = _walk(value)
        if out.get("type") == "object" and "properties" in out:
            out["additionalProperties"] = False
            # Strict mode requires every property be required.
            properties = out.get("properties", {})
            if isinstance(properties, dict):
                out["required"] = list(properties.keys())
        return out
    if isinstance(node, list):
        return [_walk(item) for item in node]
    return node
