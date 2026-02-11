"""Validate playbooks against the playbook schema."""
from __future__ import annotations

import json
import os
from typing import Any, Dict, List

try:
    import yaml  # type: ignore
except Exception as exc:
    raise RuntimeError("PyYAML is required to validate playbooks.") from exc

try:
    from jsonschema import Draft202012Validator  # type: ignore
except Exception as exc:
    raise RuntimeError("jsonschema is required to validate playbooks.") from exc


def load_schema(path: str) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as handle:
        return json.load(handle)


def _is_list_of_strings(value: Any) -> bool:
    return isinstance(value, list) and all(isinstance(item, str) for item in value)


def _error_details(error: Any) -> str:
    path = ".".join(str(part) for part in error.absolute_path) or "<root>"
    return f"{path}: {error.message}"


def _validate_references(data: Dict[str, Any]) -> List[str]:
    errors: List[str] = []
    phases = data.get("phases", [])
    allowed_external = {"classify_failure", "gate_rerun", "apply_promotion"}
    for item in data.get("gate_requirements", []):
        phase = item.get("phase")
        if phase not in phases:
            errors.append(f"gate_requirements phase not in phases: {phase}")
        gates = item.get("gates")
        if not _is_list_of_strings(gates):
            errors.append(f"gate_requirements gates must be list of strings for phase {phase}")
    for item in data.get("allowed_loops", []):
        from_phase = item.get("from_phase")
        to_phase = item.get("to_phase")
        if from_phase not in phases and from_phase not in allowed_external:
            errors.append(f"allowed_loops from_phase not in phases: {from_phase}")
        if to_phase not in phases and to_phase not in allowed_external:
            errors.append(f"allowed_loops to_phase not in phases: {to_phase}")
        if not isinstance(item.get("max_iterations"), int):
            errors.append(f"allowed_loops max_iterations must be int for {from_phase}")
        if not isinstance(item.get("trigger_condition"), str):
            errors.append(f"allowed_loops trigger_condition must be string for {from_phase}")
    return errors


def main() -> int:
    repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    schema_path = os.path.join(repo_root, "schemas", "playbook.schema.json")
    playbook_dir = os.path.join(repo_root, "playbooks")

    schema = load_schema(schema_path)
    validator = Draft202012Validator(schema)
    failures = 0
    for name in os.listdir(playbook_dir):
        if not name.endswith(".yaml"):
            continue
        path = os.path.join(playbook_dir, name)
        with open(path, "r", encoding="utf-8") as handle:
            data = yaml.safe_load(handle)
        if not isinstance(data, dict):
            failures += 1
            print(f"FAIL {name}: playbook must be a mapping/object at the top level")
            continue
        schema_errors = sorted(validator.iter_errors(data), key=lambda item: list(item.path))
        ref_errors = _validate_references(data)
        if schema_errors or ref_errors:
            failures += 1
            details = []
            details.extend(_error_details(error) for error in schema_errors[:3])
            details.extend(ref_errors)
            print(f"FAIL {name}: " + "; ".join(details))
        else:
            print(f"OK   {name}")

    if failures:
        print(f"\n{failures} playbook(s) failed validation.")
        return 1
    print("\nAll playbooks passed validation.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
