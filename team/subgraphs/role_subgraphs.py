"""Role subgraph stubs that write artifacts via the StateBroker."""
from __future__ import annotations

from typing import Any, Dict, List, Set, Tuple

from team.engine.state_broker import StateBroker


def _skill_info(state: Dict[str, Any]) -> Dict[str, Any]:
    info = state.get("skill_context", {})
    if not isinstance(info, dict):
        return {"names": [], "instructions": ""}
    names = info.get("names", [])
    instructions = info.get("instructions", "")
    if not isinstance(names, list):
        names = []
    if not isinstance(instructions, str):
        instructions = ""
    adaptive_memories = info.get("adaptive_memories", [])
    if not isinstance(adaptive_memories, list):
        adaptive_memories = []
    return {"names": names, "instructions": instructions, "adaptive_memories": adaptive_memories}


def _with_skill_metadata(payload: Dict[str, Any], state: Dict[str, Any]) -> Dict[str, Any]:
    skill = _skill_info(state)
    if skill["names"]:
        payload["skill_names"] = skill["names"]
    if skill["instructions"]:
        payload["skill_instructions"] = skill["instructions"]
    if skill["adaptive_memories"]:
        payload["adaptive_memories"] = skill["adaptive_memories"]
    return payload


def _default_system_spec(runtime_target: str) -> Dict[str, Any]:
    return {
        "version": 0,
        "runtime_target": runtime_target,
        "topology_type": "DAG" if runtime_target == "langgraph" else "hybrid",
        "core": {
            "state_schema": {},
            "components": [],
            "contracts": {},
            "safety_reliability": {},
            "failure_modes": [],
        },
        "langgraph_ext": {},
        "deepagent_ext": {},
        "hybrid_ext": {},
    }


def _default_prompt_pack() -> Dict[str, Any]:
    return {
        "version": 0,
        "system_prompts": {},
        "role_prompts": {},
        "tool_patterns": {},
        "guardrails": [],
        "few_shots": [],
    }


def _default_tool_contract() -> Dict[str, Any]:
    return {
        "version": 0,
        "tools": [],
        "retries": {},
        "caching": {},
        "idempotency": {},
        "rate_limits": {},
    }


def _default_eval_spec() -> Dict[str, Any]:
    return {
        "version": 0,
        "datasets": [],
        "metrics": [],
        "thresholds": {},
        "rubrics": [],
    }


def _default_experiment_report() -> Dict[str, Any]:
    return {
        "version": 0,
        "scores": {},
        "failure_clusters": [],
        "comparisons": [],
    }


def _default_experiment_spec() -> Dict[str, Any]:
    return {
        "version": 0,
        "variants": [],
        "metrics": [],
        "controls": [],
    }


def _default_promotion_decision() -> Dict[str, Any]:
    return {
        "id": "optimizer-default",
        "proposer": "optimizer",
        "target_artifact": "PromptPack",
        "proposed_changes": [
            {"op": "set", "path": "optimization.last_run", "value": "optimizer-default"}
        ],
        "justification": ["baseline optimization promotion for scaffold routing"],
        "confidence": 0.55,
        "urgency": "low",
    }


def _default_telemetry_spec() -> Dict[str, Any]:
    return {
        "version": 0,
        "metrics": [],
        "sampling": {},
        "traces": {},
    }


def _default_slo_report() -> Dict[str, Any]:
    return {
        "version": 0,
        "pass": True,
        "violations": [],
        "failure_signals": {},
    }


def _default_compiled_spec(runtime_target: str) -> Dict[str, Any]:
    return {
        "version": 0,
        "runtime_target": runtime_target,
        "config": {},
        "code_stubs": [],
    }


def _default_compilation_report() -> Dict[str, Any]:
    return {
        "version": 0,
        "warnings": [],
        "assumptions": [],
        "errors": [],
    }


def _latest_or_default(
    broker: StateBroker, artifact_type: str, default: Dict[str, Any]
) -> Dict[str, Any]:
    version = broker.latest_version(artifact_type)
    if version == 0:
        return default
    return broker.read_full(artifact_type, version)


def _component_tool_names(component: Dict[str, Any]) -> List[str]:
    names: List[str] = []
    usage = component.get("tool_usage", [])
    if isinstance(usage, list):
        for item in usage:
            if isinstance(item, str):
                names.append(item)
            elif isinstance(item, dict):
                tool_name = item.get("tool") or item.get("name") or item.get("id")
                if isinstance(tool_name, str):
                    names.append(tool_name)
    return names


def _tool_contract_names(tool_contract: Dict[str, Any]) -> Set[str]:
    names: Set[str] = set()
    tools = tool_contract.get("tools", [])
    if isinstance(tools, list):
        for item in tools:
            if isinstance(item, str):
                names.add(item)
            elif isinstance(item, dict):
                tool_name = item.get("name") or item.get("id")
                if isinstance(tool_name, str):
                    names.add(tool_name)
    return names


def _validate_compilation_inputs(
    system_spec: Dict[str, Any], prompt_pack: Dict[str, Any], tool_contract: Dict[str, Any]
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], List[str]]:
    errors: List[Dict[str, Any]] = []
    warnings: List[Dict[str, Any]] = []
    assumptions: List[str] = []

    core = system_spec.get("core", {})
    components = core.get("components", [])
    if not isinstance(components, list):
        errors.append(
            {
                "error_type": "schema_inconsistency",
                "details": "core.components must be a list of component objects",
            }
        )
        return errors, warnings, assumptions

    component_ids: Set[str] = set()
    for component in components:
        if not isinstance(component, dict):
            errors.append({"error_type": "schema_inconsistency", "details": "component must be an object"})
            continue
        component_id = component.get("id")
        if not isinstance(component_id, str) or not component_id:
            errors.append({"error_type": "schema_inconsistency", "details": "component missing non-empty id"})
            continue
        component_ids.add(component_id)

    for component in components:
        if not isinstance(component, dict):
            continue
        component_id = str(component.get("id", "<unknown>"))
        inputs = component.get("inputs", [])
        if not isinstance(inputs, list):
            continue
        for inbound in inputs:
            if not isinstance(inbound, dict):
                continue
            source = inbound.get("from_component")
            if isinstance(source, str) and source and source not in component_ids:
                errors.append(
                    {
                        "error_type": "schema_inconsistency",
                        "details": f"component {component_id} references unknown from_component {source}",
                    }
                )

    contract_names = _tool_contract_names(tool_contract)
    for component in components:
        if not isinstance(component, dict):
            continue
        component_id = str(component.get("id", "<unknown>"))
        for tool_name in _component_tool_names(component):
            if tool_name not in contract_names:
                errors.append(
                    {
                        "error_type": "missing_contract",
                        "details": f"component {component_id} uses uncovered tool {tool_name}",
                    }
                )

    state_schema = core.get("state_schema", {})
    schema_keys = set(state_schema.keys()) if isinstance(state_schema, dict) else set()
    written_keys: Set[str] = set()
    for component in components:
        if not isinstance(component, dict):
            continue
        writes = component.get("state_writes", [])
        if isinstance(writes, list):
            for key in writes:
                if isinstance(key, str):
                    written_keys.add(key)
    for component in components:
        if not isinstance(component, dict):
            continue
        component_id = str(component.get("id", "<unknown>"))
        reads = component.get("state_reads", [])
        if not isinstance(reads, list):
            continue
        for key in reads:
            if isinstance(key, str) and key not in schema_keys and key not in written_keys:
                errors.append(
                    {
                        "error_type": "schema_inconsistency",
                        "details": f"component {component_id} reads unwritten state key {key}",
                    }
                )

    for component in components:
        if not isinstance(component, dict):
            continue
        component_id = str(component.get("id", "<unknown>"))
        budget = component.get("budget_defaults")
        if budget is None:
            budget = component.get("budget")
        if not isinstance(budget, dict):
            errors.append(
                {
                    "error_type": "schema_inconsistency",
                    "details": f"component {component_id} missing budget defaults",
                }
            )
            continue
        for field in ("max_steps", "max_tokens", "max_tool_calls"):
            if field not in budget:
                errors.append(
                    {
                        "error_type": "schema_inconsistency",
                        "details": f"component {component_id} missing budget field {field}",
                    }
                )

    runtime_target = str(system_spec.get("runtime_target", "langgraph"))
    if runtime_target == "hybrid":
        hybrid_ext = system_spec.get("hybrid_ext", {})
        boundary_contracts = []
        if isinstance(hybrid_ext, dict):
            boundary_contracts = hybrid_ext.get("boundary_contracts", [])
        if not isinstance(boundary_contracts, list):
            errors.append(
                {
                    "error_type": "boundary_mismatch",
                    "details": "hybrid_ext.boundary_contracts must be a list",
                }
            )
        else:
            for contract in boundary_contracts:
                if not isinstance(contract, dict):
                    errors.append(
                        {"error_type": "boundary_mismatch", "details": "boundary contract must be an object"}
                    )
                    continue
                if not isinstance(contract.get("graph_side"), dict) or not isinstance(
                    contract.get("recursion_side"), dict
                ):
                    errors.append(
                        {
                            "error_type": "boundary_mismatch",
                            "details": "boundary contract missing graph_side or recursion_side",
                        }
                    )

    role_prompts = prompt_pack.get("role_prompts", {})
    prompt_keys = set(role_prompts.keys()) if isinstance(role_prompts, dict) else set()
    for component in components:
        if not isinstance(component, dict):
            continue
        if not component.get("requires_prompt", False):
            continue
        prompt_key = component.get("prompt_id") or component.get("id")
        if isinstance(prompt_key, str) and prompt_key not in prompt_keys:
            errors.append(
                {
                    "error_type": "prompt_gap",
                    "details": f"component {component.get('id', '<unknown>')} requires missing prompt {prompt_key}",
                }
            )

    if not components:
        warnings.append({"warning_type": "empty_components", "details": "SystemSpec has no components to compile"})
        assumptions.append("Compilation proceeded with empty component list.")

    return errors, warnings, assumptions


def run_architect(state: Dict[str, Any], broker: StateBroker) -> Dict[str, Any]:
    spec = _default_system_spec(state.get("runtime_target", "langgraph"))
    spec = _with_skill_metadata(spec, state)
    version = broker.write("SystemSpec", spec, author="architect")
    return {"artifact": "SystemSpec", "version": version}


def run_prompt_policy(state: Dict[str, Any], broker: StateBroker) -> Dict[str, Any]:
    pack = _default_prompt_pack()
    skill = _skill_info(state)
    if skill["instructions"]:
        pack["role_prompts"]["skill_context"] = skill["instructions"]
    pack = _with_skill_metadata(pack, state)
    version = broker.write("PromptPack", pack, author="prompt_policy")
    return {"artifact": "PromptPack", "version": version}


def run_tooling(state: Dict[str, Any], broker: StateBroker) -> Dict[str, Any]:
    contract = _default_tool_contract()
    contract = _with_skill_metadata(contract, state)
    version = broker.write("ToolContract", contract, author="tooling")
    return {"artifact": "ToolContract", "version": version}


def run_eval(state: Dict[str, Any], broker: StateBroker) -> Dict[str, Any]:
    eval_spec = _default_eval_spec()
    report = _default_experiment_report()
    eval_spec = _with_skill_metadata(eval_spec, state)
    report = _with_skill_metadata(report, state)
    eval_version = broker.write("EvalSpec", eval_spec, author="eval")
    report_version = broker.write("ExperimentReport", report, author="eval")
    return {
        "artifact": "ExperimentReport",
        "version": report_version,
        "eval_spec_version": eval_version,
        "quality_gate_output": {"pass": True, "score": 1.0, "failure_signals": {}},
    }


def run_optimizer(state: Dict[str, Any], broker: StateBroker) -> Dict[str, Any]:
    spec = _default_experiment_spec()
    decision = _default_promotion_decision()
    spec = _with_skill_metadata(spec, state)
    decision = _with_skill_metadata(decision, state)
    spec_version = broker.write("ExperimentSpec", spec, author="optimizer")
    decision_version = broker.write("PromotionDecision", decision, author="optimizer")
    return {"artifact": "PromotionDecision", "version": decision_version, "experiment_spec_version": spec_version}


def run_ops(state: Dict[str, Any], broker: StateBroker) -> Dict[str, Any]:
    telemetry = _default_telemetry_spec()
    slo = _default_slo_report()
    telemetry = _with_skill_metadata(telemetry, state)
    slo = _with_skill_metadata(slo, state)
    telemetry_version = broker.write("TelemetrySpec", telemetry, author="ops")
    slo_version = broker.write("SLOReport", slo, author="ops")
    return {
        "artifact": "SLOReport",
        "version": slo_version,
        "telemetry_version": telemetry_version,
        "production_gate_output": {"pass": True, "violations": [], "failure_signals": {}},
    }


def run_compiler(state: Dict[str, Any], broker: StateBroker) -> Dict[str, Any]:
    runtime_target = state.get("runtime_target", "langgraph")
    system_spec = _latest_or_default(broker, "SystemSpec", _default_system_spec(str(runtime_target)))
    prompt_pack = _latest_or_default(broker, "PromptPack", _default_prompt_pack())
    tool_contract = _latest_or_default(broker, "ToolContract", _default_tool_contract())

    errors, warnings, assumptions = _validate_compilation_inputs(system_spec, prompt_pack, tool_contract)
    compiled = _default_compiled_spec(str(runtime_target))
    compiled["config"] = {
        "runtime_target": runtime_target,
        "topology_type": system_spec.get("topology_type"),
        "components": system_spec.get("core", {}).get("components", []),
    }
    compiled["code_stubs"] = ["# STUB: implement runtime adapters"]
    compiled = _with_skill_metadata(compiled, state)

    report = _default_compilation_report()
    report["warnings"] = warnings
    report["assumptions"] = assumptions
    report["errors"] = errors
    report = _with_skill_metadata(report, state)
    compiled_version = broker.write("CompiledSpec", compiled, author="compiler")
    report_version = broker.write("CompilationReport", report, author="compiler")
    return {
        "artifact": "CompiledSpec",
        "version": compiled_version,
        "report_version": report_version,
        "compilation_errors": errors,
    }
