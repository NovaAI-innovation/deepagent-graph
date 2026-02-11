"""Skill loading and hook execution utilities."""
from __future__ import annotations

import os
from typing import Any, Dict, List

try:
    import yaml  # type: ignore
except Exception as exc:
    raise RuntimeError("PyYAML is required to load skills.") from exc


ALLOWED_EVENTS = {"pre_run", "pre_phase", "post_phase"}


def _deep_merge(base: Dict[str, Any], patch: Dict[str, Any]) -> Dict[str, Any]:
    for key, value in patch.items():
        if isinstance(value, dict) and isinstance(base.get(key), dict):
            _deep_merge(base[key], value)
        else:
            base[key] = value
    return base


def _as_list(value: Any) -> List[str]:
    if not value:
        return []
    if isinstance(value, list):
        return [str(item) for item in value]
    return [str(value)]


def _hook_matches(hook: Dict[str, Any], event: str, context: Dict[str, Any]) -> bool:
    if hook.get("event") != event:
        return False
    roles = _as_list(hook.get("roles"))
    if roles and context.get("role") not in roles:
        return False
    playbooks = _as_list(hook.get("playbooks"))
    if playbooks and context.get("playbook") not in playbooks:
        return False
    phases = _as_list(hook.get("phases"))
    if phases and context.get("phase") not in phases:
        return False
    runtimes = _as_list(hook.get("runtime_targets"))
    if runtimes and context.get("runtime_target") not in runtimes:
        return False
    return True


def _validate_skill_doc(doc: Dict[str, Any], path: str) -> List[str]:
    errors: List[str] = []
    if not isinstance(doc, dict):
        return [f"{path}: skill must be a top-level mapping/object"]
    if not isinstance(doc.get("name"), str) or not doc.get("name"):
        errors.append(f"{path}: missing non-empty 'name'")
    hooks = doc.get("hooks")
    if not isinstance(hooks, list):
        errors.append(f"{path}: 'hooks' must be a list")
        return errors
    top_level_roles = _as_list(doc.get("roles"))
    for idx, hook in enumerate(hooks):
        if not isinstance(hook, dict):
            errors.append(f"{path}: hook[{idx}] must be an object")
            continue
        event = hook.get("event")
        if event not in ALLOWED_EVENTS:
            errors.append(f"{path}: hook[{idx}] has invalid event '{event}'")
        hook_roles = _as_list(hook.get("roles"))
        if hook_roles and top_level_roles:
            errors.append(f"{path}: hook[{idx}] cannot define both top-level roles and hook roles")
        actions = hook.get("actions")
        if not isinstance(actions, dict):
            errors.append(f"{path}: hook[{idx}] missing object 'actions'")
    return errors


def load_skills(skills_dir: str) -> List[Dict[str, Any]]:
    if not os.path.isdir(skills_dir):
        return []
    loaded: List[Dict[str, Any]] = []
    for name in sorted(os.listdir(skills_dir)):
        if not name.endswith(".yaml"):
            continue
        path = os.path.join(skills_dir, name)
        with open(path, "r", encoding="utf-8") as handle:
            doc = yaml.safe_load(handle)
        if not isinstance(doc, dict):
            continue
        if doc.get("enabled", True) is False:
            continue
        loaded.append(doc)
    return loaded


def validate_skill_files(skills_dir: str) -> List[str]:
    if not os.path.isdir(skills_dir):
        return []
    errors: List[str] = []
    for name in sorted(os.listdir(skills_dir)):
        if not name.endswith(".yaml"):
            continue
        path = os.path.join(skills_dir, name)
        with open(path, "r", encoding="utf-8") as handle:
            doc = yaml.safe_load(handle)
        errors.extend(_validate_skill_doc(doc, path))
    return errors


def apply_skill_hooks(
    skills: List[Dict[str, Any]],
    event: str,
    context: Dict[str, Any],
    request: Dict[str, Any],
    budgets: Dict[str, Any],
) -> List[str]:
    notes: List[str] = []
    for skill in skills:
        skill_name = str(skill.get("name", "unnamed"))
        hooks = skill.get("hooks", [])
        if not isinstance(hooks, list):
            continue
        for hook in hooks:
            if not isinstance(hook, dict):
                continue
            if not _hook_matches(hook, event, context):
                continue
            actions = hook.get("actions", {})
            if not isinstance(actions, dict):
                continue

            request_patch = actions.get("request_patch")
            if isinstance(request_patch, dict):
                _deep_merge(request, request_patch)

            user_constraints_patch = actions.get("user_constraints_patch")
            if isinstance(user_constraints_patch, dict):
                user_constraints = request.setdefault("user_constraints", {})
                if not isinstance(user_constraints, dict):
                    request["user_constraints"] = {}
                    user_constraints = request["user_constraints"]
                _deep_merge(user_constraints, user_constraints_patch)

            budget_patch = actions.get("budget_patch")
            if isinstance(budget_patch, dict):
                _deep_merge(budgets, budget_patch)

            note = actions.get("routing_note")
            if isinstance(note, str) and note:
                notes.append(f"{skill_name}: {note}")
            else:
                notes.append(f"{skill_name}: {event} hook applied")
    return notes


def hook_target_roles(skills: List[Dict[str, Any]]) -> List[str]:
    roles = set()
    for skill in skills:
        top_roles = set(_as_list(skill.get("roles")))
        hooks = skill.get("hooks", [])
        if not isinstance(hooks, list):
            continue
        for hook in hooks:
            if not isinstance(hook, dict):
                continue
            hook_roles = set(_as_list(hook.get("roles")))
            effective = hook_roles or top_roles or {"orchestrator"}
            for role in effective:
                roles.add(role)
    return sorted(roles)
