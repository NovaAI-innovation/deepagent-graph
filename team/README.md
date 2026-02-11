# Team v2 Scaffold

This folder contains the multi-agent team scaffold for langgraph, deepagent, and hybrid targets.

## Layout
- engine/: core orchestration utilities (state broker, gates, classifier)
- roles/: lead role prompts
- subgraphs/: role subgraph stubs
- workers/: worker template and registry
- playbooks/: playbook phase definitions
- runtime/: compiled spec stubs for each runtime
- prompts/: PromptPack template
- templates/: artifact templates
- schemas/: JSON schemas for core artifacts
- scripts/: validation helpers
- state_broker/: file-backed artifact storage for the scaffold

## Usage
- Update PromptPack in prompts/ and role prompts in roles/ as you specialize behavior.
- Use templates/ as starting points for artifact creation.
- Fill runtime compiled spec stubs during compilation.
- Use schemas/ for lightweight validation in your tooling pipeline.
- Install `pyyaml` to load and validate playbooks in the orchestrator and scripts.
