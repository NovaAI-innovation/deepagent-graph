# Repository Guidelines

## Project Structure & Module Organization
- `team/` contains the working scaffold.
- `team/orchestrator/` holds the meta-orchestrator entrypoint (`orchestrator.py`) and graph metadata.
- `team/engine/` contains core orchestration utilities (state broker, gates, failure routing, config).
- `team/subgraphs/` and `team/roles/` define role-level stubs and role instructions.
- `team/playbooks/` stores workflow definitions; `team/schemas/` and `team/templates/` pair JSON schemas with YAML templates.
- `team/state_broker/` is file-backed runtime output (artifacts, summaries, logs).
- `plan/` stores planning docs for v2 design work.

## Build, Test, and Development Commands
- `pip install -r requirements.txt` installs validation/runtime dependencies.
- `python team/scripts/run_checks.py` runs playbook and template schema validations in one pass.
- `python team/scripts/run_checks.py --with-smoke` runs validations plus an orchestrator smoke run.
- `python team/orchestrator/orchestrator.py --repo C:\Users\casey\deepagent-graph --playbook build` runs the scaffold orchestrator directly.

## Coding Style & Naming Conventions
- Follow Python 3 style with 4-space indentation, type hints, and small focused functions.
- Keep module names `snake_case.py`, classes `PascalCase`, functions/variables `snake_case`.
- Preserve existing docstring style and explicit return codes in script `main()` functions.
- Keep YAML and schema filenames aligned by artifact name (example: `eval_spec.schema.json` and `eval_spec.yaml`).

## Testing Guidelines
- Current validation is script-based (no dedicated unit test suite yet).
- Before opening a PR, run `python team/scripts/run_checks.py` (or `--with-smoke` for execution coverage).
- When adding checks, keep failure output actionable (include file name and missing/invalid fields).

## Commit & Pull Request Guidelines
- This snapshot does not include `.git` history; use Conventional Commit style (for example: `feat(engine): add gate reroute cap`).
- Keep commits scoped to one concern (orchestrator logic, schema/template updates, or docs).
- PRs should include: purpose, affected paths, validation commands run, and sample output when behavior changes.
- Link related issues and include updated artifacts/screenshots only when they clarify review.

## Security & Configuration Tips
- Do not commit secrets or environment-specific credentials.
- Treat `team/state_broker/artifacts/` as generated state; review diffs carefully before committing.
