"""Validate skill files against the skill schema and local invariants."""
from __future__ import annotations

import json
import os
import sys
from typing import Any, Dict

try:
    import yaml  # type: ignore
except Exception as exc:
    raise RuntimeError("PyYAML is required to validate skills.") from exc

try:
    from jsonschema import Draft202012Validator  # type: ignore
except Exception as exc:
    raise RuntimeError("jsonschema is required to validate skills.") from exc

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from team.engine.skills import validate_skill_files
from team.engine.system_profile import load_system_profile, resolve_skills_dir


def _load_schema(path: str) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as handle:
        return json.load(handle)


def _error_details(error: Any) -> str:
    path = ".".join(str(part) for part in error.absolute_path) or "<root>"
    return f"{path}: {error.message}"


def main() -> int:
    repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    profile = load_system_profile(REPO_ROOT)
    skills_dir = resolve_skills_dir(REPO_ROOT, profile)
    schema_path = os.path.join(repo_root, "schemas", "skill.schema.json")
    if not os.path.isdir(skills_dir):
        print(f"FAIL skills directory does not exist: {skills_dir}")
        return 1

    schema = _load_schema(schema_path)
    validator = Draft202012Validator(schema)
    failures = 0

    for name in sorted(os.listdir(skills_dir)):
        if not name.endswith(".yaml"):
            continue
        path = os.path.join(skills_dir, name)
        with open(path, "r", encoding="utf-8") as handle:
            doc = yaml.safe_load(handle)
        if not isinstance(doc, dict):
            failures += 1
            print(f"FAIL {name}: skill must be a mapping/object")
            continue
        errors = sorted(validator.iter_errors(doc), key=lambda item: list(item.path))
        if errors:
            failures += 1
            summary = "; ".join(_error_details(error) for error in errors[:3])
            print(f"FAIL {name}: {summary}")
        else:
            print(f"OK   {name}")

    local_errors = validate_skill_files(skills_dir)
    for error in local_errors:
        failures += 1
        print(f"FAIL invariant: {error}")

    if failures:
        print(f"\n{failures} skill validation error(s) found.")
        return 1
    print("\nAll skills passed validation.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
