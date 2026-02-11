"""Enforce role-level exclusivity: hook YAML or markdown skills, not both."""
from __future__ import annotations

import os
import sys
from typing import Dict, List

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from team.engine.md_skills import load_markdown_skills, markdown_target_roles
from team.engine.skills import hook_target_roles, load_skills
from team.engine.system_profile import load_system_profile, resolve_skills_dir


def main() -> int:
    profile = load_system_profile(REPO_ROOT)
    skills_cfg: Dict[str, object] = profile.get("skills", {}) if isinstance(profile.get("skills"), dict) else {}
    declared_modes: Dict[str, str] = (
        skills_cfg.get("role_mode", {}) if isinstance(skills_cfg.get("role_mode"), dict) else {}
    )
    declared_roles: List[str] = sorted(str(role) for role in declared_modes.keys())
    skills_dir = resolve_skills_dir(REPO_ROOT, profile)
    yaml_skills = load_skills(skills_dir)
    md_skills = load_markdown_skills(skills_dir)

    hook_roles = set(hook_target_roles(yaml_skills))
    md_roles = set(markdown_target_roles(md_skills, all_roles=declared_roles))

    require_declared = bool(skills_cfg.get("require_declared_roles", True))
    if require_declared:
        undeclared = sorted((hook_roles.union(md_roles)).difference(set(declared_roles)))
        if undeclared:
            print("FAIL undeclared role targets detected:")
            for role in undeclared:
                print(f"- {role}")
            return 1

    enforce_exclusive = bool(skills_cfg.get("enforce_exclusive", True))
    if enforce_exclusive:
        overlap = sorted(hook_roles.intersection(md_roles))
        if overlap:
            print("FAIL role exclusivity violation:")
            print("Roles configured with both hook and markdown skills:")
            for role in overlap:
                print(f"- {role}")
            return 1

    mode_failures: List[str] = []
    for role, mode_raw in declared_modes.items():
        role_name = str(role)
        mode = str(mode_raw).strip().lower()
        has_hook = role_name in hook_roles
        has_md = role_name in md_roles
        if mode == "hook" and not has_hook:
            mode_failures.append(f"{role_name}: mode=hook but no hook skill targets this role")
        if mode == "hook" and has_md:
            mode_failures.append(f"{role_name}: mode=hook but markdown skills target this role")
        if mode == "markdown" and not has_md:
            mode_failures.append(f"{role_name}: mode=markdown but no markdown skill targets this role")
        if mode == "markdown" and has_hook:
            mode_failures.append(f"{role_name}: mode=markdown but hook skills target this role")
        if mode == "none" and (has_hook or has_md):
            mode_failures.append(f"{role_name}: mode=none but skills still target this role")
        if mode not in {"hook", "markdown", "none"}:
            mode_failures.append(f"{role_name}: invalid mode '{mode_raw}'")

    if mode_failures:
        print("FAIL role mode policy violations:")
        for item in mode_failures:
            print(f"- {item}")
        return 1

    print("Skill exclusivity and role mode policy checks passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
