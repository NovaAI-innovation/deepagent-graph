"""File-backed state broker with versioned artifacts and summaries."""
from __future__ import annotations

import json
import os
import time
from typing import Any, Dict, Optional

from .config import ARTIFACT_OWNERS


class StateBroker:
    def __init__(self, storage_dir: str) -> None:
        self.storage_dir = storage_dir
        self.artifact_dir = os.path.join(storage_dir, "artifacts")
        self.summary_dir = os.path.join(storage_dir, "summaries")
        self.meta_eval_log = os.path.join(storage_dir, "meta_eval_log.jsonl")
        os.makedirs(self.artifact_dir, exist_ok=True)
        os.makedirs(self.summary_dir, exist_ok=True)

    def _artifact_path(self, artifact_type: str, version: int) -> str:
        filename = f"{artifact_type}_v{version}.json"
        return os.path.join(self.artifact_dir, filename)

    def _summary_path(self, artifact_type: str, version: int) -> str:
        filename = f"{artifact_type}_v{version}.summary.json"
        return os.path.join(self.summary_dir, filename)

    def _latest_version(self, artifact_type: str) -> int:
        prefix = f"{artifact_type}_v"
        versions = []
        for name in os.listdir(self.artifact_dir):
            if not name.startswith(prefix):
                continue
            try:
                version_part = name.split("_v", 1)[1].split(".", 1)[0]
                versions.append(int(version_part))
            except ValueError:
                continue
        return max(versions) if versions else 0

    def latest_version(self, artifact_type: str) -> int:
        return self._latest_version(artifact_type)

    def _summarize(self, artifact_type: str, value: Dict[str, Any]) -> Dict[str, Any]:
        purpose_map = {
            "SystemSpec": "Architecture source of truth.",
            "PromptPack": "Prompts and policies.",
            "ToolContract": "Tool schemas and reliability rules.",
            "EvalSpec": "Evaluation datasets and metrics.",
            "ExperimentReport": "Evaluation results and failure clusters.",
            "ExperimentSpec": "Experiment plan.",
            "TelemetrySpec": "Telemetry definitions.",
            "SLOReport": "Production gate results.",
            "PromotionDecision": "Cross-artifact change proposal.",
            "ConstraintPack": "Pre-phase constraints.",
            "CompiledSpec": "Runtime-specific compiled spec.",
            "CompilationReport": "Compiler warnings and assumptions.",
            "MetaEvalLog": "Meta-system performance log.",
        }
        key_fields = {}
        for field in ("runtime_target", "topology_type", "pass", "score", "urgency"):
            if field in value:
                key_fields[field] = value.get(field)
        return {
            "artifact_type": artifact_type,
            "version": value.get("version"),
            "purpose": purpose_map.get(artifact_type, "Artifact summary."),
            "key_fields": key_fields,
            "keys": sorted(list(value.keys())),
            "timestamp": int(time.time()),
        }

    def write(self, artifact_type: str, value: Dict[str, Any], author: str) -> int:
        owner = ARTIFACT_OWNERS.get(artifact_type)
        if owner and owner != author:
            raise PermissionError(f"{author} cannot write {artifact_type}; owner is {owner}.")
        current_version = self._latest_version(artifact_type)
        new_version = current_version + 1
        value = dict(value)
        value["version"] = new_version
        path = self._artifact_path(artifact_type, new_version)
        with open(path, "w", encoding="utf-8") as handle:
            json.dump(value, handle, indent=2)
        summary = self._summarize(artifact_type, value)
        with open(self._summary_path(artifact_type, new_version), "w", encoding="utf-8") as handle:
            json.dump(summary, handle, indent=2)
        return new_version

    def read_full(self, artifact_type: str, version: Optional[int] = None) -> Dict[str, Any]:
        if version is None:
            version = self._latest_version(artifact_type)
        path = self._artifact_path(artifact_type, version)
        with open(path, "r", encoding="utf-8") as handle:
            return json.load(handle)

    def read_summary(self, artifact_type: str, version: Optional[int] = None) -> Dict[str, Any]:
        if version is None:
            version = self._latest_version(artifact_type)
        path = self._summary_path(artifact_type, version)
        with open(path, "r", encoding="utf-8") as handle:
            return json.load(handle)

    def read_for_role(self, artifact_type: str, role: str, version: Optional[int] = None) -> Dict[str, Any]:
        owner = ARTIFACT_OWNERS.get(artifact_type)
        if owner == role:
            return self.read_full(artifact_type, version)
        return self.read_summary(artifact_type, version)

    def read_section(self, artifact_type: str, section_path: str, version: Optional[int] = None) -> Any:
        data = self.read_full(artifact_type, version)
        value: Any = data
        for key in section_path.split("."):
            if isinstance(value, dict):
                value = value.get(key)
            else:
                return None
        return value

    def append_meta_eval(self, entry: Dict[str, Any]) -> None:
        with open(self.meta_eval_log, "a", encoding="utf-8") as handle:
            handle.write(json.dumps(entry) + "\n")
