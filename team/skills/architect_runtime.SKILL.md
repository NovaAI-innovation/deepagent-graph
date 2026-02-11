---
name: architect_runtime_skill
roles: [architect]
playbooks: [build, debug, optimize, hardening, incident_response, evaluate_only]
runtime_targets: [langgraph, deepagent, hybrid]
---
# Architect Runtime Skill

- Keep `SystemSpec` runtime-aware and explicit about `runtime_target`.
- Prefer deterministic state ownership and clear `state_reads`/`state_writes`.
- For `hybrid`, include boundary contracts and failure propagation details.
- Ensure every component includes budget defaults and tool usage intent.
