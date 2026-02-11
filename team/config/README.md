# System Profile

`system_profile.yaml` is the template control plane for adapting this repo to other domains/frameworks.

## What to edit
- `domain`: your target domain (for example `customer_support`, `healthcare_ops`).
- `framework`: your orchestration style identifier.
- `defaults.runtime_target`: default runtime (`langgraph`, `deepagent`, `hybrid`).
- `defaults.playbook`: default playbook name.
- `memory`: adaptive memory backend and write/read policy.
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

## Memory backends
- `noop`: disabled.
- `inmemory`: local process memory (development only).
- `mem0`: Mem0 adaptive memory with configurable local vector store.

## Mem0 with local vector DB
Set:
- `memory.enabled: true`
- `memory.backend: mem0`
- `memory.mem0.vector_store` config (for example local Qdrant on `localhost:6333`).

Example:
```yaml
memory:
  enabled: true
  backend: mem0
  top_k: 5
  min_score_to_record: 0.75
  user_id: local-user
  agent_id: deepagent-graph
  mem0:
    vector_store:
      provider: qdrant
      config:
        host: localhost
        port: 6333
```

Local Qdrant helper:
```bash
docker compose -f infra/docker-compose.qdrant.yml up -d
```
