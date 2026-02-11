# Cross-Cutting Operating Model v2 (Not Roles, Not Graph Topology)

This document captures the **shared rules, artifacts, gates, and operating practices** that apply across the system.
It intentionally avoids duplicating role definitions or graph node lists.

---

## 1) Artifacts & Ownership Rules

### 1.1 Core artifacts

| Artifact | Owner | Description |
|---|---|---|
| `SystemSpec` | Architect | Source-of-truth architecture (core + runtime extensions) |
| `PromptPack` | Prompt/Policy | Prompts, policies, guardrails |
| `ToolContract` | Tooling | Tool schemas, reliability rules, retry/caching policies |
| `EvalSpec` | Eval | Datasets, metrics, thresholds, rubrics |
| `ExperimentSpec` | Optimizer | Experiment plan (what to vary, what to measure) |
| `ExperimentReport` | Eval | Results, scores, failure clusters |
| `TelemetrySpec` | Ops | What to log, cost/latency metric definitions |
| `SLOReport` | Ops | Production gate results |
| `PromotionDecision` | Optimizer | Proposed cross-artifact change + justification |
| `ConstraintPack` | Orchestrator | Lightweight pre-phase constraint signals |
| `CompiledSpec` | Compiler | Runtime-specific realization of SystemSpec |
| `CompilationReport` | Compiler | Warnings, assumptions, ambiguities from compilation |
| `MetaEvalLog` | Orchestrator | Append-only log of meta-system performance metrics |

### 1.2 Ownership + write rules
- Each artifact has a **single owning lead** (see table above).
- Non-owning agents treat all artifacts as **read-only**.
- Cross-artifact changes are done exclusively via the **Promotion Protocol** (§6).
- The State Broker enforces ownership at write time — unauthorized writes are rejected and logged.

### 1.3 Artifact versioning
- Every artifact carries a `version` field (monotonic integer).
- Every write increments the version.
- State references include `{artifact_type, version}` so consumers know exactly which version they read.
- Breaking schema changes require a new major version and migration logic in the State Broker.

---

## 2) Budgeting & Controls

### 2.1 Budget dimensions
Budgets are enforced across four dimensions:
- `max_steps`: total reasoning/action steps
- `max_tokens`: total token consumption (input + output)
- `max_tool_calls`: total external tool invocations
- `max_spawns`: total sub-agent worker spawns

### 2.2 Budget allocation strategy
- Set a **global** budget and **per-role** sub-budgets (see graph doc §14 for concrete profiles).
- Default to conservative caps for recursion-heavy runtimes (deepagent/hybrid): reduce `max_spawns` by 30%, reduce `max_steps` by 20% compared to langgraph baseline.
- Require explicit justification (logged in routing_trace) to exceed caps.

### 2.3 Budget exhaustion protocol
When a role exhausts any budget dimension:

1. **Yield with progress**: Role returns `status: budget_exhausted`, its partial output, and an estimate of remaining work.
2. **Orchestrator triage**:
   - If partial output is usable (passes minimum viability check): proceed, log warning.
   - If not usable: check for reallocation headroom.
3. **Reallocation**: Orchestrator may reallocate up to 50% of underspent budget from other roles that have completed or are significantly under-budget.
4. **Escalation**: If reallocation insufficient, trigger `gate_human` (or auto-finalize in autonomous mode with `status: partial`).

### 2.4 Budget monitoring
The Orchestrator tracks budget consumption after every phase and logs:
- Per-role: consumed vs allocated (all four dimensions)
- Global: consumed vs total
- Burn rate: tokens/steps per phase (for anomaly detection)

---

## 3) Gates (Objective Supervision)

### 3.1 Quality Gate (Eval)
**Inputs:** Artifacts from the current phase + EvalSpec
**Outputs (structured):**
- `pass`: bool
- `score`: float (0.0–1.0)
- `failure_clusters[]`: grouped failure descriptions with counts
- `failure_signals`: structured data for the failure classifier (tool_errors, state_anomalies, routing_anomalies, metric_failures)
- `recommended_fix_route`: suggestion (non-binding; actual routing is done by `classify_failure`)

### 3.2 Production Gate (Ops)
**Inputs:** Artifacts + TelemetrySpec + SLO targets
**Outputs (structured):**
- `pass`: bool
- `violations[]`: `{metric, threshold, actual, severity}`
- `failure_signals`: structured data for the failure classifier
- `recommended_fix_route`: suggestion (non-binding)

### 3.3 Human Gate (optional)
**Inputs:** Current artifact summaries, gate results, routing trace, specific decision points
**Outputs:**
- `decision`: approve | reject | override_budget | terminate | inject_constraints
- `feedback`: structured text (routed to specified role if reject)
- `constraint_additions`: added to ConstraintPack if inject_constraints

**Activation conditions:**
- Playbook explicitly requires it at this phase
- A role subgraph flagged `needs_human_review: true`
- Budget exhaustion with no reallocation possible
- Quality gate score in ambiguous band (configurable, default 0.4–0.7)

**Autonomous mode:** Auto-approves, logs the review request for post-hoc inspection.

### 3.4 Gate rule
No promotion to "done" without passing all required gates for the chosen playbook. Gate requirements are defined per-playbook in playbook metadata.

---

## 4) Failure Classification (Structured Heuristics)

### 4.1 Principle
Failure **routing** is deterministic. Failure **classification** is structured-heuristic (not LLM-based, not vibes-based).

### 4.2 Classification inputs
The `classify_failure` node receives `failure_signals` from gate outputs:
- `tool_errors[]`: `{tool_name, error_type, count}` — types: schema_mismatch, auth_failure, timeout, logic_error, rate_limit
- `state_anomalies[]`: `{key, anomaly_type}` — types: unexpected_write, type_mismatch, unbounded_growth, missing_key
- `routing_anomalies[]`: `{anomaly_type, details}` — types: loop_detected, dead_end_reached, unreachable_node
- `metric_failures[]`: `{metric_name, expected, actual, category}` — categories: reasoning, instruction_following, tool_use, latency, cost, coverage
- `compilation_errors[]`: `{error_type, details}` — types: schema_inconsistency, missing_contract, unbounded_recursion, boundary_mismatch

### 4.3 Classification rules (ordered, first match wins)

| Priority | Condition | Route to |
|---|---|---|
| 1 | Any `tool_errors` with type schema_mismatch/auth_failure/timeout/rate_limit | Tooling |
| 2 | Any `routing_anomalies` (loop/dead_end/unreachable) | Architect |
| 3 | Any `state_anomalies` (unexpected_write/type_mismatch/growth) | Architect |
| 4 | Any `compilation_errors` with type schema_inconsistency/unbounded_recursion | Architect |
| 5 | Any `compilation_errors` with type missing_contract | Tooling |
| 6 | `metric_failures` where category is coverage/rubric | Eval |
| 7 | `metric_failures` where category is reasoning/instruction_following | Prompt/Policy |
| 8 | `metric_failures` where category is latency/cost | Ops |
| 9 | `tool_errors` with type logic_error | Prompt/Policy |
| 10 | No rules match | Architect (default) |

### 4.4 Multi-match logging
When multiple rules match, the highest-priority rule wins. All matching rules are logged in `routing_trace` for meta-evaluation. Persistent multi-match patterns indicate systemic issues.

### 4.5 Taxonomy versioning
The classification rules are versioned. Changes to the taxonomy require:
- A justification logged in MetaEvalLog
- Re-running a representative set of past failures through the new taxonomy to check for regressions

---

## 5) Playbooks (Operational Templates)

### 5.1 Available playbooks
- Build
- Debug
- Optimize
- Evaluate-only
- Hardening
- Incident response

### 5.2 Playbook metadata (required for each)
Every playbook must define:

| Field | Description |
|---|---|
| `phases[]` | Ordered list of phases with role assignments |
| `entry_preconditions` | Required artifacts and their minimum state |
| `gate_requirements` | Which gates are required at which phase exits |
| `allowed_loops[]` | `{from_phase, to_phase, max_iterations, trigger_condition}` |
| `termination_conditions` | Success criteria, failure criteria, budget exhaustion behavior |
| `human_gate_placement` | required | optional | skip — at which phases |
| `gather_constraints` | bool — whether to run constraint gathering (default true) |

### 5.3 Loop discipline
All loops must be:
- Explicitly declared in playbook metadata
- Capped with `max_iterations` (recommended default: 3)
- Tracked in state: `loop_counts: {loop_id: current_count}`
- Logged in routing_trace with iteration number and trigger reason

When a loop reaches its cap:
- If partial progress was made: proceed to next phase with warning
- If no progress: escalate to `gate_human` or fail with structured error

---

## 6) Promotion Protocol (Cross-Artifact Mutation)

### 6.1 Problem statement
Roles like the Optimizer may recommend changes to artifacts they don't own (e.g., SystemSpec, PromptPack). Direct mutation violates ownership. Ignoring the recommendation wastes optimization work.

### 6.2 The PromotionDecision artifact
Produced by the proposing role (typically Optimizer):
```
PromotionDecision:
  id: unique
  proposer: role_id
  target_artifact: artifact_type
  proposed_changes: structured diff (field-level, not prose)
  justification: metric evidence (before/after or predicted impact)
  confidence: float (0.0–1.0)
  urgency: low | medium | high
```

### 6.3 Workflow

```
Proposer creates PromotionDecision
  → Orchestrator receives it, adds to active_promotions queue
  → Orchestrator dispatches to apply_promotion node
  → apply_promotion routes to OWNING LEAD of target_artifact
  → Owning lead evaluates:
    - ACCEPT: applies changes, increments artifact version, returns new version
    - REJECT: returns structured reason (e.g., "conflicts with safety constraint X")
    - MODIFY: applies changes with modifications, returns new version + explanation
  → Orchestrator logs outcome
  → If accepted/modified: affected gates re-run
  → If rejected: logged, pipeline continues
```

### 6.4 Rules
- No artifact is ever mutated by a non-owner.
- PromotionDecision is a **request**, not a command.
- Owning leads may reject for any reason, but must provide structured justification.
- Repeated rejections (3+ for same target) are flagged in MetaEvalLog for human review.

---

## 7) Bounded Sub-Agent Rules

### 7.1 Capabilities
Sub-agents (workers) may:
- Research (read artifacts via State Broker summaries)
- Draft (produce candidate outputs)
- Test (run evaluations on candidates)
- Summarize (compress information)

### 7.2 Constraints
Sub-agents must NOT:
- Directly update global artifacts (must return to owning lead)
- Make decisions (propose options, don't choose)
- Spawn their own sub-agents (one level of delegation only)
- Access full artifact payloads (summaries only, unless lead explicitly grants full access)

### 7.3 Behavioral rules
- Return structured outputs only
- Stop early when confidence is high (don't exhaust budget for marginal improvement)
- Escalate to the owning lead when blocked or uncertain
- Include confidence scores in all outputs

### 7.4 Spawn caps (starting point)

| Role | max_spawns | Rationale |
|---|---|---|
| Architect | 5 | Topology, state, failure mode reviewers |
| Eval | 5 | Case generation, rubric writing, clustering |
| Optimizer | 5 | Ablation design, results analysis, tradeoff analysis |
| Prompt/Policy | 4 | Variant generation, policy testing, edge-case probing |
| Tooling | 3 | Schema validation, adapter generation, reliability testing |
| Compiler | 3 | Code generation, validation, boundary adapter generation |
| Ops | 2 | Prefer deterministic analysis over exploration |

---

## 8) State Management (Context & Memory)

### 8.1 State Broker
An infrastructure component (not an agent) that mediates all artifact access.

### 8.2 Storage model
- Artifacts stored by `(artifact_type, version)` — immutable once written (new version on change)
- Full payloads stored externally (not serialized in graph state)
- Graph state carries `artifact_ref: {type, version, summary_hash}`

### 8.3 Access patterns

| Pattern | Who uses it | What it returns |
|---|---|---|
| `read_full(type)` | Owning lead, deep analysis | Complete artifact |
| `read_summary(type)` | Non-owners, workers | ~500 token summary |
| `read_section(type, path)` | Targeted queries | Specific section/field |
| `write(type, value, author)` | Owning lead only | New version number |

### 8.4 Summarization
- Summaries are generated on write (by the State Broker, using a fast model)
- Cached and invalidated on new version
- Summary format is standardized: purpose, key decisions, open questions, version

### 8.5 History management
- History entries: `{phase, role, decision, outcome, timestamp}`
- Max 50 active entries
- Overflow: oldest 25 compressed into single summary entry
- Full history always in State Broker for post-hoc analysis

---

## 9) Versioning & Regression Discipline

### 9.1 Artifact versioning
- All artifacts carry monotonic `version` counters
- Schema changes are versioned separately from content changes
- Breaking schema changes require migration logic

### 9.2 Regression anchors
- `EvalSpec` + baseline `ExperimentReport` serve as regression anchors
- Every PromotionDecision that is accepted triggers a regression run: minimum eval suite re-executed against the updated artifact
- Regression failure blocks the promotion (owning lead must decide: revert or fix forward)

### 9.3 Changelog
Every artifact write logs:
- What changed (field-level diff)
- Why (linked to PromotionDecision or phase output)
- Metric impact (before/after, if available)

### 9.4 Meta-system versioning
The following meta-system components are also versioned:
- Failure classification taxonomy (§4)
- Budget profiles (graph doc §14)
- Playbook definitions (§5)
- Gate thresholds

Changes to meta-system components follow the same discipline: justification, changelog, regression check.

---

## 10) Meta-Evaluation (System Self-Assessment)

### 10.1 Purpose
The meta-system must evaluate its own performance, not just the systems it designs.

### 10.2 Tracked metrics

| Metric | What it measures | Warning threshold |
|---|---|---|
| Route accuracy | % of failure classifications that led to successful fix on first reroute | < 60% |
| Budget utilization | Actual spend / allocated per role | > 90% (too tight) or < 30% (wasteful) |
| Gate false positive rate | Gates that pass but downstream phase fails | > 15% |
| Gate false negative rate | Gates that fail but rerouted fix was unnecessary | > 20% |
| Loop count distribution | Retry loops per playbook run | Mean > 2 per run |
| Time-to-compile | Phases before first successful compile | > 8 phases |
| Promotion acceptance rate | Accepted / total PromotionDecisions | < 40% (misalignment) |
| Human escalation rate | % of runs requiring human gate | Track trend, no fixed threshold |

### 10.3 Collection
- Logged automatically by the Orchestrator to `MetaEvalLog` (append-only)
- No gates on MetaEvalLog — it's observational, not blocking
- Periodic human review (recommended: after every 10 runs or weekly, whichever is sooner)

### 10.4 Acting on meta-evaluation
When metrics breach warning thresholds:
- Failure taxonomy: review and update classification rules
- Budget profiles: adjust allocations based on utilization data
- Gate thresholds: recalibrate ambiguity bands
- Playbook design: restructure phases or add/remove loops

---

## 11) Implementation Order (Bootstrapping)

Recommended order for building the factory:

1. Define artifact JSON schemas + validation (SystemSpec with runtime extensions, PromptPack, EvalSpec, ToolContract, ConstraintPack, PromotionDecision, CompiledSpec)
2. Implement State Broker (storage, access control, summarization, versioning)
3. Implement Meta Orchestrator graph + playbook runner + budget enforcement
4. Implement `classify_failure` with initial rule set
5. Implement `gather_constraints` node
6. Implement ArchitectSubgraph → SystemSpec
7. Implement EvalSubgraph → smoke + regression reports
8. Add Prompt/Policy + Tooling subgraphs
9. Add Optimizer subgraph + Promotion Protocol
10. Add Ops subgraph + production gate
11. Add Compiler subgraph (with validation)
12. Add Human Gate (can be stubbed as auto-approve earlier)
13. Add meta-evaluation logging + dashboard
14. Tune budget profiles and failure taxonomy based on initial runs
