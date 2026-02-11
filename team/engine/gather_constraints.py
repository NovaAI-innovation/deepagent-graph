"""Constraint gathering stub."""
from __future__ import annotations

from typing import Any, Dict


def gather_constraints(request: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "version": 0,
        "eval_constraints": request.get("eval_constraints", {}),
        "tool_constraints": request.get("tool_constraints", {}),
        "ops_constraints": request.get("ops_constraints", {}),
        "user_constraints": request.get("user_constraints", request),
    }
