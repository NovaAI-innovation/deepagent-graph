"""Validate template YAML files against JSON schemas."""
from __future__ import annotations

import json
import os
from typing import Any, Dict, List

try:
    import yaml  # type: ignore
except Exception as exc:
    raise RuntimeError("PyYAML is required to validate templates.") from exc

try:
    from jsonschema import Draft202012Validator  # type: ignore
except Exception as exc:
    raise RuntimeError("jsonschema is required to validate templates.") from exc


def _load_schema(schema_path: str) -> Dict[str, Any]:
    with open(schema_path, "r", encoding="utf-8") as handle:
        return json.load(handle)


def _load_yaml(template_path: str) -> Dict[str, Any]:
    with open(template_path, "r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle)
    if not isinstance(data, dict):
        raise ValueError(f"{template_path} must contain a top-level mapping/object.")
    return data


def _error_details(error: Any) -> str:
    path = ".".join(str(part) for part in error.absolute_path) or "<root>"
    return f"{path}: {error.message}"


def main() -> int:
    repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    schema_dir = os.path.join(repo_root, "schemas")
    template_dir = os.path.join(repo_root, "templates")

    mapping = {
        "constraint_pack.schema.json": "constraint_pack.yaml",
        "system_spec.schema.json": "system_spec.yaml",
        "tool_contract.schema.json": "tool_contract.yaml",
        "eval_spec.schema.json": "eval_spec.yaml",
        "experiment_report.schema.json": "experiment_report.yaml",
        "experiment_spec.schema.json": "experiment_spec.yaml",
        "promotion_decision.schema.json": "promotion_decision.yaml",
        "telemetry_spec.schema.json": "telemetry_spec.yaml",
        "slo_report.schema.json": "slo_report.yaml",
        "compilation_report.schema.json": "compilation_report.yaml",
        "compiled_spec.schema.json": "compiled_spec.yaml",
        "prompt_pack.schema.json": "prompt_pack.yaml",
    }

    failures = 0
    for schema_file, template_file in mapping.items():
        schema_path = os.path.join(schema_dir, schema_file)
        template_path = os.path.join(template_dir, template_file)
        schema = _load_schema(schema_path)
        data = _load_yaml(template_path)
        validator = Draft202012Validator(schema)
        errors = sorted(validator.iter_errors(data), key=lambda item: list(item.path))
        if errors:
            failures += 1
            summary = "; ".join(_error_details(error) for error in errors[:3])
            print(f"FAIL {template_file}: {summary}")
        else:
            print(f"OK   {template_file}")

    if failures:
        print(f"\n{failures} template(s) failed schema validation.")
        return 1
    print("\nAll templates passed schema validation.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
