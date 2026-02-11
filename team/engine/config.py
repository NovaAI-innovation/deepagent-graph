"""Shared configuration for the team scaffold."""
from __future__ import annotations

from typing import Dict


ARTIFACT_OWNERS: Dict[str, str] = {
    "SystemSpec": "architect",
    "PromptPack": "prompt_policy",
    "ToolContract": "tooling",
    "EvalSpec": "eval",
    "ExperimentSpec": "optimizer",
    "ExperimentReport": "eval",
    "TelemetrySpec": "ops",
    "SLOReport": "ops",
    "PromotionDecision": "optimizer",
    "ConstraintPack": "orchestrator",
    "CompiledSpec": "compiler",
    "CompilationReport": "compiler",
    "MetaEvalLog": "orchestrator",
}

STANDARD_BUILD_BUDGETS = {
    "global": {
        "max_steps": 100,
        "max_tokens": 500000,
        "max_tool_calls": 200,
        "max_spawns": 30,
    },
    "per_role": {
        "architect": {"max_steps": 15, "max_tokens": 80000, "max_tool_calls": 30, "max_spawns": 5},
        "prompt_policy": {"max_steps": 10, "max_tokens": 60000, "max_tool_calls": 20, "max_spawns": 4},
        "tooling": {"max_steps": 10, "max_tokens": 40000, "max_tool_calls": 30, "max_spawns": 3},
        "eval": {"max_steps": 20, "max_tokens": 100000, "max_tool_calls": 50, "max_spawns": 5},
        "optimizer": {"max_steps": 15, "max_tokens": 80000, "max_tool_calls": 30, "max_spawns": 5},
        "ops": {"max_steps": 8, "max_tokens": 30000, "max_tool_calls": 15, "max_spawns": 2},
        "compiler": {"max_steps": 10, "max_tokens": 60000, "max_tool_calls": 15, "max_spawns": 3},
        "orchestrator": {"max_steps": 12, "max_tokens": 50000, "max_tool_calls": 10, "max_spawns": 0},
    },
}

FAILURE_TAXONOMY_VERSION = 1
