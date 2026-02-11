"""Promotion protocol handling with ownership-enforced artifact updates."""
from __future__ import annotations

from copy import deepcopy
from typing import Any, Dict, List, Tuple

from .config import ARTIFACT_OWNERS


def _split_path(path: str) -> List[str]:
    return [part for part in path.split(".") if part]


def _set_path(payload: Dict[str, Any], path: str, value: Any) -> bool:
    parts = _split_path(path)
    if not parts:
        return False
    node: Dict[str, Any] = payload
    for part in parts[:-1]:
        child = node.get(part)
        if not isinstance(child, dict):
            child = {}
            node[part] = child
        node = child
    node[parts[-1]] = value
    return True


def _delete_path(payload: Dict[str, Any], path: str) -> bool:
    parts = _split_path(path)
    if not parts:
        return False
    node: Dict[str, Any] = payload
    for part in parts[:-1]:
        child = node.get(part)
        if not isinstance(child, dict):
            return False
        node = child
    if parts[-1] not in node:
        return False
    del node[parts[-1]]
    return True


def _merge_dict(base: Dict[str, Any], patch: Dict[str, Any]) -> Dict[str, Any]:
    merged = deepcopy(base)
    for key, value in patch.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _merge_dict(merged[key], value)
        else:
            merged[key] = value
    return merged


def _apply_changes(current: Dict[str, Any], changes: List[Dict[str, Any]]) -> Tuple[Dict[str, Any], int, int]:
    updated = deepcopy(current)
    applied = 0
    ignored = 0
    for change in changes:
        if not isinstance(change, dict):
            ignored += 1
            continue
        op = str(change.get("op", "set"))
        path = str(change.get("path", "")).strip()
        if op == "set":
            if _set_path(updated, path, change.get("value")):
                applied += 1
            else:
                ignored += 1
            continue
        if op == "delete":
            if _delete_path(updated, path):
                applied += 1
            else:
                ignored += 1
            continue
        if op == "merge":
            value = change.get("value")
            if not path or not isinstance(value, dict):
                ignored += 1
                continue
            target = updated
            for part in _split_path(path):
                child = target.get(part)
                if not isinstance(child, dict):
                    child = {}
                    target[part] = child
                target = child
            merged = _merge_dict(target, value)
            target.clear()
            target.update(merged)
            applied += 1
            continue
        ignored += 1
    return updated, applied, ignored


def apply_promotion(promotion: Dict[str, Any], broker: Any) -> Dict[str, Any]:
    target = promotion.get("target_artifact")
    owner = ARTIFACT_OWNERS.get(target, "unknown")
    if owner == "unknown":
        return {
            "target_artifact": target,
            "owner": owner,
            "decision": "rejected",
            "notes": "Unknown target artifact; cannot route promotion.",
            "new_version": None,
        }
    latest_version = broker.latest_version(target)
    if latest_version == 0:
        return {
            "target_artifact": target,
            "owner": owner,
            "decision": "rejected",
            "notes": "Target artifact does not exist yet.",
            "new_version": None,
        }
    changes = promotion.get("proposed_changes", [])
    if not isinstance(changes, list) or not changes:
        return {
            "target_artifact": target,
            "owner": owner,
            "decision": "rejected",
            "notes": "No proposed_changes supplied.",
            "new_version": None,
        }
    current = broker.read_full(target, latest_version)
    updated, applied, ignored = _apply_changes(current, changes)
    if applied == 0:
        return {
            "target_artifact": target,
            "owner": owner,
            "decision": "rejected",
            "notes": "No valid changes could be applied.",
            "new_version": None,
        }
    new_version = broker.write(target, updated, author=owner)
    decision = "accepted" if ignored == 0 else "modified"
    return {
        "target_artifact": target,
        "owner": owner,
        "decision": decision,
        "notes": f"Applied {applied} change(s); ignored {ignored}.",
        "new_version": new_version,
    }
