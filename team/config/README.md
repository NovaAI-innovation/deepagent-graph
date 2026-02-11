# System Profile

`system_profile.yaml` is the template control plane for adapting this repo to other domains/frameworks.

## What to edit
- `domain`: your target domain (for example `customer_support`, `healthcare_ops`).
- `framework`: your orchestration style identifier.
- `defaults.runtime_target`: default runtime (`langgraph`, `deepagent`, `hybrid`).
- `defaults.playbook`: default playbook name.
- `skills.directory`: where skills are loaded from.
- `skills.role_mode`: per-role mode (`hook`, `markdown`, `none`).

## Rules
- A role in `hook` mode should only be targeted by YAML hook skills.
- A role in `markdown` mode should only be targeted by Markdown `SKILL.md` files.
- A role in `none` mode must not be targeted by any skills.

Validate profile and policy with:
```bash
python team/scripts/run_checks.py
```
