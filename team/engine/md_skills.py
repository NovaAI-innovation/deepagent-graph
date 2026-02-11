"""Markdown skill loading and selection for role/phase execution."""
from __future__ import annotations

import os
from typing import Any, Dict, List, Tuple

try:
    import yaml  # type: ignore
except Exception as exc:
    raise RuntimeError("PyYAML is required to parse markdown skill frontmatter.") from exc


def _as_list(value: Any) -> List[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item) for item in value]
    return [str(value)]


def _parse_frontmatter(text: str) -> Tuple[Dict[str, Any], str]:
    if not text.startswith("---\n"):
        return {}, text
    end = text.find("\n---\n", 4)
    if end < 0:
        return {}, text
    raw = text[4:end]
    body = text[end + 5 :]
    parsed = yaml.safe_load(raw)
    if not isinstance(parsed, dict):
        return {}, body
    return parsed, body


def load_markdown_skills(skills_dir: str) -> List[Dict[str, Any]]:
    if not os.path.isdir(skills_dir):
        return []
    loaded: List[Dict[str, Any]] = []
    for root, _, files in os.walk(skills_dir):
        for name in sorted(files):
            if not name.lower().endswith(".md"):
                continue
            if name.lower() == "readme.md":
                continue
            path = os.path.join(root, name)
            with open(path, "r", encoding="utf-8") as handle:
                text = handle.read()
            frontmatter, body = _parse_frontmatter(text)
            if frontmatter.get("enabled", True) is False:
                continue
            loaded.append(
                {
                    "name": str(frontmatter.get("name", os.path.splitext(name)[0])),
                    "path": path,
                    "roles": _as_list(frontmatter.get("roles")),
                    "phases": _as_list(frontmatter.get("phases")),
                    "playbooks": _as_list(frontmatter.get("playbooks")),
                    "runtime_targets": _as_list(frontmatter.get("runtime_targets")),
                    "body": body.strip(),
                }
            )
    return loaded


def validate_markdown_skills(skills_dir: str) -> List[str]:
    errors: List[str] = []
    for skill in load_markdown_skills(skills_dir):
        if not skill.get("name"):
            errors.append(f"{skill.get('path')}: missing skill name")
        if not skill.get("body"):
            errors.append(f"{skill.get('path')}: empty skill body")
    return errors


def _matches(skill: Dict[str, Any], role: str, phase: str, playbook: str, runtime_target: str) -> bool:
    roles = skill.get("roles", [])
    if roles and role not in roles:
        return False
    phases = skill.get("phases", [])
    if phases and phase not in phases:
        return False
    playbooks = skill.get("playbooks", [])
    if playbooks and playbook not in playbooks:
        return False
    runtimes = skill.get("runtime_targets", [])
    if runtimes and runtime_target not in runtimes:
        return False
    return True


def resolve_markdown_skill_context(
    skills: List[Dict[str, Any]],
    *,
    role: str,
    phase: str,
    playbook: str,
    runtime_target: str,
) -> Dict[str, Any]:
    selected = [
        skill
        for skill in skills
        if _matches(skill, role=role, phase=phase, playbook=playbook, runtime_target=runtime_target)
    ]
    names = [str(skill["name"]) for skill in selected]
    blocks = [f"## {skill['name']}\n{skill['body']}" for skill in selected if skill.get("body")]
    instructions = "\n\n".join(blocks).strip()
    return {"names": names, "instructions": instructions}


def markdown_target_roles(skills: List[Dict[str, Any]], all_roles: List[str] | None = None) -> List[str]:
    roles = set()
    for skill in skills:
        role_filters = skill.get("roles", [])
        if role_filters:
            for role in role_filters:
                roles.add(str(role))
            continue
        if all_roles:
            for role in all_roles:
                roles.add(str(role))
    return sorted(roles)
