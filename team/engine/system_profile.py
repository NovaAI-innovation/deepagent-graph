"""System profile loader for domain/framework and skill-mode configuration."""
from __future__ import annotations

import os
from typing import Any, Dict

try:
    import yaml  # type: ignore
except Exception as exc:
    raise RuntimeError("PyYAML is required to load system profiles.") from exc


def _default_profile() -> Dict[str, Any]:
    return {
        "version": 1,
        "domain": "generic",
        "framework": "runtime_agnostic_multi_agent",
        "defaults": {"runtime_target": "langgraph", "playbook": "build"},
        "memory": {
            "enabled": False,
            "backend": "noop",
            "top_k": 3,
            "min_score_to_record": 0.7,
            "user_id": "default-user",
            "agent_id": "deepagent-graph",
        },
        "skills": {
            "directory": "team/skills",
            "enforce_exclusive": True,
            "require_declared_roles": True,
            "role_mode": {},
        },
    }


def load_system_profile(repo_root: str) -> Dict[str, Any]:
    override = os.getenv("SYSTEM_PROFILE_PATH", "").strip()
    if override:
        path = override if os.path.isabs(override) else os.path.join(repo_root, override)
    else:
        path = os.path.join(repo_root, "team", "config", "system_profile.yaml")
    if not os.path.isfile(path):
        return _default_profile()
    with open(path, "r", encoding="utf-8") as handle:
        doc = yaml.safe_load(handle)
    if not isinstance(doc, dict):
        return _default_profile()
    merged = _default_profile()
    for key, value in doc.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key].update(value)
        else:
            merged[key] = value
    if not isinstance(merged.get("skills"), dict):
        merged["skills"] = _default_profile()["skills"]
    if not isinstance(merged["skills"].get("role_mode"), dict):
        merged["skills"]["role_mode"] = {}
    return merged


def resolve_skills_dir(repo_root: str, profile: Dict[str, Any]) -> str:
    rel = profile.get("skills", {}).get("directory", "team/skills")
    rel_text = str(rel)
    if os.path.isabs(rel_text):
        return rel_text
    return os.path.join(repo_root, rel_text)


def role_skill_mode(profile: Dict[str, Any], role: str) -> str:
    mapping = profile.get("skills", {}).get("role_mode", {})
    if not isinstance(mapping, dict):
        return "none"
    mode = str(mapping.get(role, "none")).strip().lower()
    if mode not in {"hook", "markdown", "none"}:
        return "none"
    return mode
