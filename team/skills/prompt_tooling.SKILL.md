---
name: prompt_tooling_skill
roles: [prompt_policy, tooling, eval, compiler, optimizer, ops]
runtime_targets: [langgraph, deepagent, hybrid]
---
# Prompt and Tooling Skill

- Keep outputs structured and machine-routable.
- Align prompt instructions to tool contract schemas and retry rules.
- Prefer explicit failure signals over prose when reporting issues.
- When changing behavior, preserve gate compatibility (`quality_gate`, `production_gate`, `compilation_gate`).
