"""Validate team/config/system_profile.yaml against its schema."""
from __future__ import annotations

import json
import os
import sys
from typing import Any, Dict

try:
    import yaml  # type: ignore
except Exception as exc:
    raise RuntimeError("PyYAML is required to validate system profile.") from exc

try:
    from jsonschema import Draft202012Validator  # type: ignore
except Exception as exc:
    raise RuntimeError("jsonschema is required to validate system profile.") from exc

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)


def _load_json(path: str) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as handle:
        return json.load(handle)


def _error_details(error: Any) -> str:
    path = ".".join(str(part) for part in error.absolute_path) or "<root>"
    return f"{path}: {error.message}"


def _validate_profile(profile_path: str, schema: Dict[str, Any]) -> int:
    if not os.path.isfile(profile_path):
        print(f"FAIL missing profile file: {profile_path}")
        return 1
    with open(profile_path, "r", encoding="utf-8") as handle:
        profile = yaml.safe_load(handle)
    if not isinstance(profile, dict):
        print(f"FAIL profile must be a top-level mapping/object: {profile_path}")
        return 1
    validator = Draft202012Validator(schema)
    errors = sorted(validator.iter_errors(profile), key=lambda item: list(item.path))
    if errors:
        for err in errors[:5]:
            print(f"FAIL {_error_details(err)} in {profile_path}")
        print(f"\n{len(errors)} profile validation error(s) found.")
        return 1
    skills_dir = profile.get("skills", {}).get("directory")
    if isinstance(skills_dir, str):
        resolved = skills_dir if os.path.isabs(skills_dir) else os.path.join(REPO_ROOT, skills_dir)
        if not os.path.isdir(resolved):
            print(f"FAIL skills.directory does not exist in {profile_path}: {resolved}")
            return 1
    return 0


def main() -> int:
    primary_profile = os.path.join(REPO_ROOT, "team", "config", "system_profile.yaml")
    docker_profile = os.path.join(REPO_ROOT, "team", "config", "system_profile.docker.yaml")
    schema_path = os.path.join(REPO_ROOT, "team", "schemas", "system_profile.schema.json")
    schema = _load_json(schema_path)
    failures = 0
    failures += _validate_profile(primary_profile, schema)
    if os.path.isfile(docker_profile):
        failures += _validate_profile(docker_profile, schema)
    if failures:
        return 1
    print("System profiles passed validation.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
