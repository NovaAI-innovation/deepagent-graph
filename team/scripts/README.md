# Scripts

- `run_checks.py` runs all repository validation checks from one command.
- `validate_system_profile.py` validates `team/config/system_profile.yaml` settings for template portability.
- `validate_templates.py` validates template YAML files against their JSON schemas.
- `validate_playbooks.py` validates playbooks against the playbook schema and cross-reference rules.
- `validate_skills.py` validates `team/skills/*.yaml` against `team/schemas/skill.schema.json`.
- `validate_markdown_skills.py` validates Markdown `SKILL.md` files used by role/phase integration.
- `validate_skill_exclusivity.py` enforces role exclusivity: a role may use hooks or markdown skills, not both.

## Usage

```bash
python team/scripts/run_checks.py
python team/scripts/run_checks.py --with-smoke
```
