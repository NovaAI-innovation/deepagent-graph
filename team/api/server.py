"""HTTP API for running playbooks via the orchestrator."""
from __future__ import annotations

import os
from typing import Any, Dict

from fastapi import FastAPI
from pydantic import BaseModel, Field

from team.orchestrator.orchestrator import Orchestrator


class RunRequest(BaseModel):
    playbook: str = Field(default="build")
    runtime: str = Field(default="langgraph")
    request: Dict[str, Any] = Field(default_factory=dict)


def _repo_root() -> str:
    return os.getenv("REPO_ROOT", os.getcwd())


app = FastAPI(title="deepagent-graph", version="0.1.0")


@app.get("/health")
def health() -> Dict[str, str]:
    return {"status": "ok"}


@app.post("/run")
def run(payload: RunRequest) -> Dict[str, Any]:
    orchestrator = Orchestrator(_repo_root())
    request = dict(payload.request)
    request["runtime_target"] = payload.runtime
    result = orchestrator.run(payload.playbook, request)
    return result
