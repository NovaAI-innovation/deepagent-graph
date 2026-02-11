# Skills

Skills are runtime hook files loaded from `team/skills/*.yaml`.
Markdown skills (`*.SKILL.md`) are also loaded from the same directory.
Role behavior mode is configured in `team/config/system_profile.yaml` under `skills.role_mode`.
For each role, choose exactly one mode: `hook`, `markdown`, or `none`.

## Supported Hook Events
- `pre_run`: before playbook phases start.
- `pre_phase`: before each phase dispatch.
- `post_phase`: after each phase dispatch.

## Match Filters
Each hook can optionally constrain when it applies:
- `playbooks`: list of playbook names.
- `phases`: list of phase names.
- `runtime_targets`: list of `langgraph`, `deepagent`, `hybrid`.

## Actions
- `request_patch`: deep-merge into orchestrator request.
- `user_constraints_patch`: deep-merge into `request.user_constraints`.
- `budget_patch`: deep-merge into orchestrator budgets.
- `routing_note`: text appended to routing trace when applied.

## Validate
```bash
python team/scripts/validate_skills.py
```
