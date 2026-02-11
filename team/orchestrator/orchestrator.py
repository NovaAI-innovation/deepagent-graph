"""Meta-orchestrator skeleton with StateBroker integration."""
from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import dataclass, field
from typing import Any, Dict, List

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from team.engine.classify_failure import classify_failure  # noqa: E402
from team.engine.config import STANDARD_BUILD_BUDGETS  # noqa: E402
from team.engine.gather_constraints import gather_constraints  # noqa: E402
from team.engine.gates import human_gate, production_gate, quality_gate  # noqa: E402
from team.engine.md_skills import load_markdown_skills, resolve_markdown_skill_context  # noqa: E402
from team.engine.skills import apply_skill_hooks, load_skills  # noqa: E402
from team.engine.schema_validation import load_schema, validate_required  # noqa: E402
from team.engine.state_broker import StateBroker  # noqa: E402
from team.engine.system_profile import load_system_profile, resolve_skills_dir, role_skill_mode  # noqa: E402
from team.engine.promotion import apply_promotion  # noqa: E402
from team.subgraphs.role_subgraphs import (  # noqa: E402
    run_architect,
    run_compiler,
    run_eval,
    run_optimizer,
    run_ops,
    run_prompt_policy,
    run_tooling,
)


def _load_yaml(text: str) -> Dict[str, Any]:
    try:
        import yaml  # type: ignore
    except Exception as exc:
        raise RuntimeError("PyYAML is required to load playbooks.") from exc
    return yaml.safe_load(text)


@dataclass
class OrchestratorState:
    status: str = "running"
    routing_trace: List[Dict[str, str]] = field(default_factory=list)
    history: List[Dict[str, str]] = field(default_factory=list)
    budgets: Dict[str, Any] = field(default_factory=lambda: STANDARD_BUILD_BUDGETS.copy())
    artifacts: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    steps_used: int = 0
    budget_exhausted: bool = False
    role_steps: Dict[str, int] = field(default_factory=dict)
    loop_counts: Dict[str, int] = field(default_factory=dict)


class Orchestrator:
    def __init__(self, repo_root: str) -> None:
        self.repo_root = repo_root
        self.playbook_dir = os.path.join(repo_root, "team", "playbooks")
        self.profile = load_system_profile(repo_root)
        self.skills_dir = resolve_skills_dir(repo_root, self.profile)
        self.schema_dir = os.path.join(repo_root, "team", "schemas")
        self.state = OrchestratorState()
        storage_dir = os.path.join(repo_root, "team", "state_broker")
        self.broker = StateBroker(storage_dir)
        self.skills = load_skills(self.skills_dir)
        self.md_skills = load_markdown_skills(self.skills_dir)

    def load_playbook(self, name: str) -> Dict[str, Any]:
        path = os.path.join(self.playbook_dir, f"{name}.yaml")
        with open(path, "r", encoding="utf-8") as handle:
            text = handle.read()
        data = _load_yaml(text)
        schema_path = os.path.join(self.schema_dir, "playbook.schema.json")
        schema = load_schema(schema_path)
        validation = validate_required(schema, data)
        if not validation["valid"]:
            missing = ", ".join(validation["missing"])
            raise ValueError(f"Playbook {name} missing required keys: {missing}")
        return data

    @staticmethod
    def _allowed_loop(allowed_loops: List[Dict[str, Any]], from_phase: str, trigger: str) -> Optional[Dict[str, Any]]:
        for entry in allowed_loops:
            if entry.get("from_phase") == from_phase and entry.get("trigger_condition") == trigger:
                return entry
        return None

    @staticmethod
    def _gate_trigger(gate_name: str) -> str:
        if gate_name == "quality_gate":
            return "quality_gate_fail"
        if gate_name == "production_gate":
            return "production_gate_fail"
        if gate_name == "compilation_gate":
            return "compilation_fail"
        return "gate_fail"

    @staticmethod
    def _route_to_phase(route: str) -> str:
        mapping = {
            "architect": "architect",
            "prompt_policy": "prompt_policy",
            "tooling": "tooling",
            "eval": "eval_smoke",
            "optimizer": "optimizer",
            "ops": "ops_instrument",
            "compiler": "compile",
        }
        return mapping.get(route, "architect")

    @staticmethod
    def _phase_role(phase: str) -> str:
        if phase.startswith("eval"):
            return "eval"
        if phase.startswith("ops"):
            return "ops"
        if phase.startswith("optimizer"):
            return "optimizer"
        if phase.startswith("compile"):
            return "compiler"
        if phase.startswith("human_gate"):
            return "orchestrator"
        if phase == "gather_constraints":
            return "orchestrator"
        if phase == "prompt_policy":
            return "prompt_policy"
        if phase == "tooling":
            return "tooling"
        if phase == "architect":
            return "architect"
        if phase == "apply_promotion":
            return "orchestrator"
        return "orchestrator"

    def _record(self, phase: str, decision: str, outcome: str) -> None:
        self.state.routing_trace.append(
            {"phase": phase, "decision": decision, "reason": outcome}
        )
        self.state.history.append({"phase": phase, "decision": decision, "outcome": outcome})

    def _apply_skills(
        self, event: str, playbook_name: str, request: Dict[str, Any], phase: str = "", role: str = "orchestrator"
    ) -> None:
        if role_skill_mode(self.profile, role) != "hook":
            return
        context = {
            "playbook": playbook_name,
            "phase": phase,
            "runtime_target": request.get("runtime_target"),
            "role": role,
        }
        notes = apply_skill_hooks(self.skills, event, context, request, self.state.budgets)
        for note in notes:
            location = phase or event
            self._record(location, "skill_hook", note)

    def _consume_budget(self, role: str) -> None:
        self.state.steps_used += 1
        max_steps = self.state.budgets.get("global", {}).get("max_steps", 0)
        if max_steps and self.state.steps_used > max_steps:
            self.state.budget_exhausted = True
            self.state.status = "blocked"
        role_steps = self.state.role_steps.get(role, 0) + 1
        self.state.role_steps[role] = role_steps
        role_budget = self.state.budgets.get("per_role", {}).get(role, {})
        role_max_steps = role_budget.get("max_steps", 0)
        if role_max_steps and role_steps > role_max_steps:
            self.state.budget_exhausted = True
            self.state.status = "blocked"

    def _dispatch(self, phase: str, request: Dict[str, Any]) -> Dict[str, Any]:
        if self.state.budget_exhausted:
            self._record(phase, "budget", "exhausted")
            return {"gate_outputs": {}}
        role = self._phase_role(phase)
        runtime_target = str(request.get("runtime_target", "langgraph"))
        playbook = str(request.get("__playbook_name", "build"))
        md_context = {"names": [], "instructions": ""}
        if role_skill_mode(self.profile, role) == "markdown":
            md_context = resolve_markdown_skill_context(
                self.md_skills,
                role=role,
                phase=phase,
                playbook=playbook,
                runtime_target=runtime_target,
            )
        phase_request = dict(request)
        phase_request["skill_context"] = {
            "role": role,
            "phase": phase,
            "names": md_context["names"],
            "instructions": md_context["instructions"],
        }
        if md_context["names"]:
            self._record(phase, "skill_context", ",".join(md_context["names"]))
        self._consume_budget(role)
        if self.state.budget_exhausted:
            self._record(phase, "budget", "exhausted")
            return {"gate_outputs": {}}
        if phase == "gather_constraints":
            constraints = gather_constraints(phase_request)
            version = self.broker.write("ConstraintPack", constraints, author="orchestrator")
            self.state.artifacts["ConstraintPack"] = {"version": version}
            self._record(phase, "write", "ConstraintPack")
            return {"gate_outputs": {}}
        if phase == "architect":
            result = run_architect(phase_request, self.broker)
            self.state.artifacts[result["artifact"]] = {"version": result["version"]}
            self._record(phase, "write", result["artifact"])
            return {"gate_outputs": {}}
        if phase == "prompt_policy":
            result = run_prompt_policy(phase_request, self.broker)
            self.state.artifacts[result["artifact"]] = {"version": result["version"]}
            self._record(phase, "write", result["artifact"])
            return {"gate_outputs": {}}
        if phase == "tooling":
            result = run_tooling(phase_request, self.broker)
            self.state.artifacts[result["artifact"]] = {"version": result["version"]}
            self._record(phase, "write", result["artifact"])
            return {"gate_outputs": {}}
        if phase.startswith("eval"):
            result = run_eval(phase_request, self.broker)
            self.state.artifacts["EvalSpec"] = {"version": result["eval_spec_version"]}
            self.state.artifacts["ExperimentReport"] = {"version": result["version"]}
            self._record(phase, "write", "ExperimentReport")
            gate_output = result.get("quality_gate_output", {"pass": True, "score": 1.0})
            return {"gate_outputs": {"quality_gate": quality_gate(gate_output)}}
        if phase == "optimizer":
            result = run_optimizer(phase_request, self.broker)
            self.state.artifacts["ExperimentSpec"] = {"version": result["experiment_spec_version"]}
            self.state.artifacts["PromotionDecision"] = {"version": result["version"]}
            self._record(phase, "write", "PromotionDecision")
            return {"gate_outputs": {}}
        if phase.startswith("ops"):
            result = run_ops(phase_request, self.broker)
            self.state.artifacts["TelemetrySpec"] = {"version": result["telemetry_version"]}
            self.state.artifacts["SLOReport"] = {"version": result["version"]}
            self._record(phase, "write", "SLOReport")
            gate_output = result.get("production_gate_output", {"pass": True})
            return {"gate_outputs": {"production_gate": production_gate(gate_output)}}
        if phase == "compile" or phase.startswith("compile"):
            result = run_compiler(phase_request, self.broker)
            self.state.artifacts["CompiledSpec"] = {"version": result["version"]}
            self.state.artifacts["CompilationReport"] = {"version": result["report_version"]}
            self._record(phase, "write", "CompiledSpec")
            compilation_errors = result.get("compilation_errors", [])
            return {
                "gate_outputs": {
                    "compilation_gate": {
                        "pass": not bool(compilation_errors),
                        "failure_signals": {"compilation_errors": compilation_errors},
                    }
                }
            }
        if phase == "apply_promotion":
            latest = self.broker.latest_version("PromotionDecision")
            if latest == 0:
                self._record(phase, "apply_promotion", "none")
                return {"gate_outputs": {}}
            decision = self.broker.read_full("PromotionDecision", latest)
            routed = apply_promotion(decision, self.broker)
            target = routed.get("target_artifact")
            new_version = routed.get("new_version")
            if isinstance(target, str) and isinstance(new_version, int):
                self.state.artifacts[target] = {"version": new_version}
            self._record(phase, "apply_promotion", routed.get("decision", "unknown"))
            return {"gate_outputs": {}}
        if phase.startswith("human_gate"):
            decision = human_gate({})
            self._record(phase, "human_gate", decision["decision"])
            return {"gate_outputs": {"human_gate_optional": decision}}
        if phase == "finalize":
            self._record(phase, "finalize", "done")
            return {"gate_outputs": {}}
        self._record(phase, "dispatch", "stub")
        return {"gate_outputs": {}}

    def run(self, playbook_name: str, request: Dict[str, Any]) -> Dict[str, Any]:
        request["__playbook_name"] = playbook_name
        request["system_profile"] = {
            "domain": self.profile.get("domain", "generic"),
            "framework": self.profile.get("framework", "runtime_agnostic_multi_agent"),
        }
        playbook = self.load_playbook(playbook_name)
        self._apply_skills("pre_run", playbook_name, request, role="orchestrator")
        phases = list(playbook.get("phases", []))
        allowed_loops = playbook.get("allowed_loops", [])
        gate_requirements = playbook.get("gate_requirements", [])
        idx = 0
        while idx < len(phases):
            phase = phases[idx]
            role = self._phase_role(phase)
            self._apply_skills("pre_phase", playbook_name, request, phase=phase, role=role)
            result = self._dispatch(phase, request)
            self._apply_skills("post_phase", playbook_name, request, phase=phase, role=role)
            gate_outputs = result.get("gate_outputs", {})
            requirements = [req for req in gate_requirements if req.get("phase") == phase]
            rerouted = False
            for req in requirements:
                for gate_name in req.get("gates", []):
                    gate_output = gate_outputs.get(gate_name, {"pass": True})
                    if gate_output.get("pass", True):
                        continue
                    trigger = self._gate_trigger(gate_name)
                    loop_entry = self._allowed_loop(allowed_loops, phase, trigger)
                    if not loop_entry:
                        continue
                    count = self.state.loop_counts.get(phase, 0) + 1
                    self.state.loop_counts[phase] = count
                    if count > int(loop_entry.get("max_iterations", 0)):
                        self._record(phase, "loop_cap", "exhausted")
                        continue
                    classification = classify_failure(gate_output.get("failure_signals", {}))
                    self._record(phase, "classify_failure", classification["route"])
                    reroute_phase = self._route_to_phase(classification["route"])
                    phases.insert(idx + 1, reroute_phase)
                    phases.insert(idx + 2, phase)
                    rerouted = True
                    break
                if rerouted:
                    break
            if not rerouted:
                idx += 1
        if not self.state.budget_exhausted:
            self.state.status = "done"
        self.broker.append_meta_eval(
            {
                "status": self.state.status,
                "phases_run": len(self.state.history),
                "steps_used": self.state.steps_used,
                "role_steps": self.state.role_steps,
                "loop_counts": self.state.loop_counts,
                "artifacts_written": list(self.state.artifacts.keys()),
            }
        )
        return {
            "status": self.state.status,
            "routing_trace": self.state.routing_trace,
            "history": self.state.history,
            "artifacts": self.state.artifacts,
        }


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the meta-orchestrator skeleton")
    parser.add_argument("--repo", default=os.getcwd(), help="Repo root path")
    parser.add_argument("--playbook", default="build", help="Playbook name")
    parser.add_argument("--runtime", default="langgraph", help="Runtime target")
    args = parser.parse_args()

    orch = Orchestrator(args.repo)
    request = {"runtime_target": args.runtime}
    result = orch.run(args.playbook, request)
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
