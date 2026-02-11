"""Minimal validation helper for JSON schemas."""
from __future__ import annotations

import json
from typing import Any, Dict


def load_schema(path: str) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as handle:
        return json.load(handle)


def validate_required(schema: Dict[str, Any], payload: Dict[str, Any]) -> Dict[str, Any]:
    required = schema.get("required", [])
    missing = [key for key in required if key not in payload]
    return {"valid": not missing, "missing": missing}
