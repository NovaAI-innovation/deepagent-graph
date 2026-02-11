"""Failure classification rules based on structured signals."""
from __future__ import annotations

from typing import Any, Dict, List

from .config import FAILURE_TAXONOMY_VERSION


def _has_tool_error(failure_signals: Dict[str, Any], types: List[str]) -> bool:
    for item in failure_signals.get("tool_errors", []) or []:
        if item.get("error_type") in types:
            return True
    return False


def _has_routing_anomaly(failure_signals: Dict[str, Any]) -> bool:
    return bool(failure_signals.get("routing_anomalies", []))


def _has_state_anomaly(failure_signals: Dict[str, Any]) -> bool:
    return bool(failure_signals.get("state_anomalies", []))


def _has_compilation_error(failure_signals: Dict[str, Any], types: List[str]) -> bool:
    for item in failure_signals.get("compilation_errors", []) or []:
        if item.get("error_type") in types:
            return True
    return False


def _has_metric_category(failure_signals: Dict[str, Any], categories: List[str]) -> bool:
    for item in failure_signals.get("metric_failures", []) or []:
        if item.get("category") in categories:
            return True
    return False


def classify_failure(failure_signals: Dict[str, Any]) -> Dict[str, Any]:
    matched: List[Dict[str, Any]] = []

    if _has_tool_error(failure_signals, ["schema_mismatch", "auth_failure", "timeout", "rate_limit"]):
        matched.append({"priority": 1, "route": "tooling"})
        route = "tooling"
    elif _has_routing_anomaly(failure_signals):
        matched.append({"priority": 2, "route": "architect"})
        route = "architect"
    elif _has_state_anomaly(failure_signals):
        matched.append({"priority": 3, "route": "architect"})
        route = "architect"
    elif _has_compilation_error(failure_signals, ["schema_inconsistency", "unbounded_recursion"]):
        matched.append({"priority": 4, "route": "architect"})
        route = "architect"
    elif _has_compilation_error(failure_signals, ["missing_contract"]):
        matched.append({"priority": 5, "route": "tooling"})
        route = "tooling"
    elif _has_metric_category(failure_signals, ["coverage", "rubric"]):
        matched.append({"priority": 6, "route": "eval"})
        route = "eval"
    elif _has_metric_category(failure_signals, ["reasoning", "instruction_following"]):
        matched.append({"priority": 7, "route": "prompt_policy"})
        route = "prompt_policy"
    elif _has_metric_category(failure_signals, ["latency", "cost"]):
        matched.append({"priority": 8, "route": "ops"})
        route = "ops"
    elif _has_tool_error(failure_signals, ["logic_error"]):
        matched.append({"priority": 9, "route": "prompt_policy"})
        route = "prompt_policy"
    else:
        matched.append({"priority": 10, "route": "architect"})
        route = "architect"

    return {
        "route": route,
        "matched_rules": matched,
        "taxonomy_version": FAILURE_TAXONOMY_VERSION,
    }
