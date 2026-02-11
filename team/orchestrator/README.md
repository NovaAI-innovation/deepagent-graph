# Orchestrator Skeleton

Minimal runnable meta-orchestrator that loads playbooks, writes artifacts via the StateBroker,
and dispatches role subgraph stubs. This does not invoke any models.

## Usage

```bash
python team/orchestrator/orchestrator.py --repo C:\Users\casey\deepagent-graph --playbook build
```

## Notes
- YAML parsing requires PyYAML for playbook loading.
- Phase dispatch uses subgraph stubs; integrate role runners where needed.
- Meta graph topology is documented in `team/orchestrator/meta_graph.yaml`.
