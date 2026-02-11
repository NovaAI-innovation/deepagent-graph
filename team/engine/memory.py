"""Adaptive memory adapter interfaces and implementations."""
from __future__ import annotations

import time
from typing import Any, Dict, List, Protocol


class MemoryAdapter(Protocol):
    def fetch(self, *, role: str, phase: str, playbook: str, runtime_target: str, query: str, top_k: int) -> List[str]:
        ...

    def record(self, *, role: str, phase: str, playbook: str, runtime_target: str, outcome: Dict[str, Any]) -> None:
        ...


class NoopMemoryAdapter:
    def fetch(self, *, role: str, phase: str, playbook: str, runtime_target: str, query: str, top_k: int) -> List[str]:
        return []

    def record(self, *, role: str, phase: str, playbook: str, runtime_target: str, outcome: Dict[str, Any]) -> None:
        return None


class InMemoryAdapter:
    def __init__(self) -> None:
        self.entries: List[Dict[str, Any]] = []

    def fetch(self, *, role: str, phase: str, playbook: str, runtime_target: str, query: str, top_k: int) -> List[str]:
        candidates: List[str] = []
        for entry in reversed(self.entries):
            if entry.get("role") != role:
                continue
            if entry.get("runtime_target") != runtime_target:
                continue
            summary = str(entry.get("summary", "")).strip()
            if summary:
                candidates.append(summary)
            if len(candidates) >= top_k:
                break
        return candidates

    def record(self, *, role: str, phase: str, playbook: str, runtime_target: str, outcome: Dict[str, Any]) -> None:
        summary = str(outcome.get("summary", "")).strip()
        if not summary:
            return
        self.entries.append(
            {
                "ts": int(time.time()),
                "role": role,
                "phase": phase,
                "playbook": playbook,
                "runtime_target": runtime_target,
                "summary": summary,
                "score": outcome.get("score"),
                "pass": outcome.get("pass"),
            }
        )


class Mem0Adapter:
    def __init__(self, *, user_id: str, agent_id: str, config: Dict[str, Any] | None = None) -> None:
        self.user_id = user_id
        self.agent_id = agent_id
        self._memory: Any = None
        self._enabled = False
        try:
            from mem0 import Memory  # type: ignore
        except Exception:
            return
        try:
            if config:
                self._memory = Memory.from_config(config)
            else:
                self._memory = Memory()
            self._enabled = True
        except Exception:
            self._enabled = False

    def fetch(self, *, role: str, phase: str, playbook: str, runtime_target: str, query: str, top_k: int) -> List[str]:
        if not self._enabled or self._memory is None:
            return []
        text = f"{query}\nrole={role}\nphase={phase}\nplaybook={playbook}\nruntime={runtime_target}"
        try:
            results = self._memory.search(text, user_id=self.user_id, limit=top_k)
        except Exception:
            return []
        snippets: List[str] = []
        if isinstance(results, list):
            for item in results:
                if not isinstance(item, dict):
                    continue
                memory_text = item.get("memory") or item.get("text") or item.get("summary")
                if isinstance(memory_text, str) and memory_text.strip():
                    snippets.append(memory_text.strip())
        return snippets[:top_k]

    def record(self, *, role: str, phase: str, playbook: str, runtime_target: str, outcome: Dict[str, Any]) -> None:
        if not self._enabled or self._memory is None:
            return
        summary = str(outcome.get("summary", "")).strip()
        if not summary:
            return
        meta = {
            "agent_id": self.agent_id,
            "role": role,
            "phase": phase,
            "playbook": playbook,
            "runtime_target": runtime_target,
            "pass": outcome.get("pass"),
            "score": outcome.get("score"),
        }
        try:
            self._memory.add(summary, user_id=self.user_id, metadata=meta)
        except Exception:
            return


def build_memory_adapter(profile: Dict[str, Any]) -> MemoryAdapter:
    cfg = profile.get("memory", {})
    if not isinstance(cfg, dict):
        return NoopMemoryAdapter()
    if not bool(cfg.get("enabled", False)):
        return NoopMemoryAdapter()
    backend = str(cfg.get("backend", "noop")).strip().lower()
    if backend == "inmemory":
        return InMemoryAdapter()
    if backend == "mem0":
        user_id = str(cfg.get("user_id", "default-user"))
        agent_id = str(cfg.get("agent_id", "deepagent-graph"))
        mem0_cfg = cfg.get("mem0")
        if not isinstance(mem0_cfg, dict):
            mem0_cfg = {}
        return Mem0Adapter(user_id=user_id, agent_id=agent_id, config=mem0_cfg)
    return NoopMemoryAdapter()
