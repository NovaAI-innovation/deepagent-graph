# Graph Architecture v2 (Runtime-Agnostic: LangGraph + DeepAgents + Hybrid)

This document defines the **meta-architecture** for a specialist agent team that can design, evaluate, optimize, and harden agent systems targeting multiple runtimes:
- **LangGraph** (graph/DAG/conditional state machines)
- **DeepAgents** (recursive planner/worker/critic systems)
- **Hybrid** (LangGraph orchestration containing DeepAgent components, or vice versa)

The core idea is **Graph-of-Graphs** with a **runtime compiler layer**:
- A **Meta Orchestrator Graph** routes work and enforces budgets (no domain work).
- **Role Subgraphs** produce **structured artifacts**.
- A **Compiler Subgraph** converts an abstract **SystemSpec** into runtime-specific implementations.
- A **State Broker** manages artifact storage, access control, and summarization.

---

## 1) Meta Orchestrator Graph (Top Level)

### 1.1 Responsibilities
The Meta Orchestrator Graph handles only:
- **Intent classification** (build/debug/optimize/evaluate/harden/incident)
- **Runtime targeting** (langgraph/deepagent/hybrid)
- **Playbook selection**
- **Budget allocation** and enforcement (including exhaustion protocol)
- **Phase dispatch** to role subgraphs
- **Gating** (quality + production + optional human)
- **Termination** and packaging of outputs

It must not implement architecture or prompts itself.

### 1.2 What the Orchestrator Does NOT Do
- Write SystemSpec / PromptPack / ToolContract (delegates to owning leads)
- Classify failure types (delegates to the failure classifier function; see §8)
- Apply PromotionDecisions (delegates to artifact owners; see §9)

---

## 2) Meta State (Canonical)

### 2.1 Required state keys

- `request`: user input + constraints (quality/latency/cost/safety/compatibility)
- `intent`: build | debug | optimize | evaluate | harden | incident
- `runtime_target`: langgraph | deepagent | hybrid
- `budgets`:
  - global: `max_steps`, `max_tokens`, `max_tool_calls`, `max_spawns`
  - per_role: allocations, caps, and exhaustion policy
- `artifacts`: a dict keyed by artifact type (SystemSpec, EvalSpec, etc.) — stored as **references**, not inline (see §11)
- `status`: running | blocked | awaiting_human | done | failed
- `history`: bounded decision log (max N entries; older entries summarized)
- `routing_trace`: structured explanation of why routes were chosen (for auditability)
- `active_promotions`: pending PromotionDecision queue

### 2.2 State size discipline
- Artifacts are stored in the **State Broker** (§11), not serialized inline on every transition.
- State passed between meta nodes contains artifact **references** (IDs + version) and **summaries**, not full payloads.
- The `history` field is capped at 50 entries. When exceeded, the oldest 25 are compressed into a single summary entry by the State Broker.

---

## 3) Meta Nodes

### 3.1 Core nodes
1. `intake`
2. `classify_intent`
3. `determine_runtime_target`
4. `gather_constraints` ← **NEW**: lightweight pre-phase (see §3.2)
5. `select_playbook`
6. `allocate_budgets`
7. `run_phase(phase_id)` ← dispatch to role subgraphs
8. `classify_failure` ← **NEW**: structured failure classification (see §8)
9. `gate_quality` ← evaluation gate
10. `gate_production` ← ops gate
11. `gate_human` ← **NEW**: optional human review gate (see §10)
12. `decide_next_phase` ← deterministic routing based on gate outputs + failure classification
13. `apply_promotion` ← **NEW**: executes PromotionDecision protocol (see §9)
14. `compile_system` ← dispatches to Compiler subgraph (see §6)
15. `finalize` ← packaging + final response assembly

### 3.2 The `gather_constraints` Node
Runs before the first phase of any playbook. Collects lightweight constraint signals:
- From Eval: evaluation criteria, known hard cases, metric thresholds
- From Tooling: available tools, known reliability issues, schema constraints
- From Ops: cost/latency envelopes, SLO targets

These are **constraints**, not full artifacts. Output is a `ConstraintPack` attached to state, visible to all subsequent phases. This breaks the circular dependency where the Architect needs Eval/Tooling/Ops context that doesn't exist yet.

### 3.3 Routing shape

```
intake → classify_intent → determine_runtime_target → gather_constraints
  → select_playbook → allocate_budgets → run_phase
```

After each `run_phase`:
- if phase produced failures → `classify_failure` → `decide_next_phase`
- if phase requires quality gate → `gate_quality`
- if phase requires production gate → `gate_production`
- if phase requires human gate → `gate_human`
- else → `decide_next_phase`

`decide_next_phase` can route to:
- the next playbook phase
- a bounded retry (explicit, capped, with retry count in state)
- `apply_promotion` (when a PromotionDecision is pending)
- `compile_system` (when ready)
- `finalize` (completion)

---

## 4) Role Subgraphs (One per Lead)

Each role subgraph:
- may spawn worker sub-agents internally (bounded by budget)
- must return **structured artifacts**
- may only write to the artifact(s) it owns
- reads other artifacts via the State Broker (read-only references)

### 4.1 Role-to-artifact mapping

| Subgraph | Owns (write) | Reads |
|---|---|---|
| ArchitectSubgraph | `SystemSpec` | ConstraintPack, EvalSpec, ToolContract |
| PromptPolicySubgraph | `PromptPack` | SystemSpec, ToolContract |
| ToolingSubgraph | `ToolContract` | SystemSpec |
| EvalSubgraph | `EvalSpec`, `ExperimentReport` | SystemSpec, PromptPack, ToolContract |
| OptimizerSubgraph | `ExperimentSpec`, `PromotionDecision` | all (read-only) |
| OpsSubgraph | `TelemetrySpec`, `SLOReport` | SystemSpec, ToolContract |
| CompilerSubgraph | `CompiledSpec` | SystemSpec, PromptPack, ToolContract |

### 4.2 Runtime branching inside subgraphs
Every role subgraph must support:
- `runtime_target == "langgraph"`: generate graph-first decisions
- `runtime_target == "deepagent"`: generate recursion-first decisions
- `runtime_target == "hybrid"`: define component boundaries + contracts between both (see §7 for hybrid reference architecture)

The Meta Orchestrator should not micromanage these differences; it just passes `runtime_target`.

---

## 5) Artifact Model (Abstract → Concrete)

### 5.1 Abstract artifact (source of truth)
**SystemSpec** is the single canonical architecture artifact.

Required fields:
- `version`: monotonic version counter
- `runtime_target`: langgraph | deepagent | hybrid
- `topology_type`: DAG | conditional | recursive | supervisor-tree | swarm | hybrid

**Core section** (shared across all runtimes):
- `state_schema`: canonical shared state + per-component local state
- `components[]`:
  - `id`, `role`, `inputs`, `outputs`, `state_reads`, `state_writes`
  - `routing_rules` (conditions, guardrails)
  - `tool_usage` (what tools, when, constraints)
  - `memory_model` (short/long-term, summarization, eviction)
- `contracts`:
  - tool contracts (schemas, retries, idempotency)
  - component contracts (artifact handoffs)
- `safety_reliability`:
  - loop breakers, timeouts, spawn caps, fallback behaviors
- `failure_modes`: expected failures + detection + remediation routes

**Runtime extension sections** (only the relevant one is populated):
- `langgraph_ext`:
  - `reducers`: per-key reducer definitions
  - `conditional_edges`: condition functions + targets
  - `checkpointer_config`: persistence strategy
  - `interrupt_points`: human-in-the-loop locations
- `deepagent_ext`:
  - `planner_config`: granularity, replanning triggers
  - `critic_config`: reflection depth, acceptance criteria
  - `spawn_policy`: max depth, max breadth, termination heuristics
  - `escalation_rules`: when workers escalate to planner
- `hybrid_ext`:
  - `boundary_map`: which components are graph-managed vs recursion-managed
  - `boundary_contracts[]`: input/output/state ownership at each boundary
  - `failure_propagation`: how failures cross boundaries
  - `shared_state_protocol`: what state is shared vs. isolated

### 5.2 Concrete artifacts (compiled outputs)
Generated by `compile_system` via the Compiler subgraph:
- `LangGraphSpec`: node definitions, edge list, conditional routing functions, state type definition, reducer map, tool node wrappers — output as **structured config + code stubs**
- `DeepAgentSpec`: planner/worker/critic role configs, loop config, spawn policies, termination heuristics — output as **structured config**
- `HybridSpec`: boundary definitions, integration plan, shared state protocol, cross-boundary error handling — output as **structured config + boundary adapter stubs**

**Output format rule**: Compiled specs always produce (1) a structured JSON/YAML config and (2) optional code stubs annotated with `# STUB: implement` markers. The system produces *executable designs*, not raw prose.

### 5.3 ConstraintPack (lightweight, pre-phase)
Generated by `gather_constraints`:
- `eval_constraints`: metric names, thresholds, known hard cases
- `tool_constraints`: available tools, known flaky tools, schema requirements
- `ops_constraints`: cost ceiling, latency ceiling, reliability floor
- `user_constraints`: from the original request

Not a full artifact — a lightweight signal bag consumed by the first phase.

---

## 6) Compiler Subgraph

The compiler is a **role subgraph**, not a bare node. It has an owning lead (Compiler Lead) and can spawn workers.

### 6.1 Responsibilities
- Convert `SystemSpec` → runtime-specific `CompiledSpec`
- Validate the spec during compilation (see §6.3)
- Generate code stubs where applicable
- Produce a `CompilationReport` noting any warnings, ambiguities resolved, or assumptions made

### 6.2 Compilation outputs by runtime

**LangGraph target:**
- Node list with signatures (inputs, outputs, state reads/writes)
- Edge list (static + conditional)
- State type definition with reducer map
- Tool node wrappers with retry/caching config
- Checkpointer configuration

**DeepAgents target:**
- Planner/worker/critic role definitions
- Loop configuration (max iterations, termination conditions)
- Spawn policies (max depth, max breadth, budget per spawn)
- Escalation rules and reflection boundaries
- Termination heuristics

**Hybrid target:**
- Component classification (graph-managed vs recursion-managed)
- Boundary adapter definitions (input/output contracts)
- State synchronization protocol
- Cross-boundary failure handling
- Shared telemetry configuration

### 6.3 Validation during compile
Compiler must enforce:
- No undefined artifact handoffs between components
- No unbounded loops without loop breakers
- All tool calls covered by a ToolContract entry
- Budget defaults present for each component
- State schema consistency (no reads of unwritten keys)
- Boundary contracts complete for hybrid targets (both sides defined)

### 6.4 Compiler failure modes
Added to the failure taxonomy (§8):
- Schema inconsistency in SystemSpec → route back to Architect
- Missing ToolContract coverage → route back to Tooling
- Unbounded recursion detected → route back to Architect
- Boundary contract mismatch (hybrid) → route back to Architect

---

## 7) Hybrid Runtime Reference Architecture

Because hybrid is the most common real-world case and the hardest to get right, it gets its own section.

### 7.1 Boundary model
A hybrid system has two zones:
- **Graph zone**: managed by LangGraph. Deterministic routing, explicit state, typed edges.
- **Recursion zone**: managed by DeepAgent-style loops. Planner/worker/critic, emergent control flow, spawn-based scaling.

The boundary is where control and state cross between zones.

### 7.2 Boundary contract schema
Each boundary must define:
```
boundary_contract:
  id: string
  graph_side:
    node_id: string
    output_schema: typed
    state_writes: [keys]
  recursion_side:
    entry_point: planner | worker
    input_schema: typed
    state_reads: [keys]
  state_ownership:
    shared_keys: [keys with defined merge strategy]
    graph_owned: [keys]
    recursion_owned: [keys]
  failure_protocol:
    recursion_timeout: duration
    recursion_max_steps: int
    on_failure: fallback_node_id | escalate | fail
  telemetry:
    trace_propagation: bool
    shared_trace_id_key: string
```

### 7.3 Decision framework: what goes where
- **Graph zone** for: deterministic routing, tool orchestration, state aggregation, gating, human-in-the-loop checkpoints
- **Recursion zone** for: open-ended reasoning, multi-step planning, self-correction, tasks where the number of steps is unknown upfront
- **Rule of thumb**: if you can enumerate the paths, use graph. If you can't, use recursion.

---

## 8) Failure Classification (Explicit)

### 8.1 The classifier function
`classify_failure` is a dedicated meta node — not an LLM "vibe router" and not a bare routing table. It uses **structured heuristics** applied to gate outputs.

### 8.2 Classification inputs
- `gate_output`: pass/fail + failure details from quality or production gate
- `failure_signals`: structured data from the failing phase:
  - `tool_errors[]`: tool name, error type, count
  - `state_anomalies[]`: unexpected state keys, type mismatches, growth alerts
  - `routing_anomalies[]`: loop counts, dead-end hits, unreachable nodes
  - `metric_failures[]`: metric name, expected, actual, gap
  - `budget_status`: remaining budget per dimension

### 8.3 Classification rules (ordered, first match wins)

| Priority | Condition | Route to | Rationale |
|---|---|---|---|
| 1 | `tool_errors.count > 0` AND error type is schema/auth/timeout | Tooling | Tool infrastructure problem |
| 2 | `routing_anomalies` contains loop count > threshold | Architect | Topology allows unbounded loops |
| 3 | `state_anomalies` contains unexpected writes or type mismatches | Architect | State schema problem |
| 4 | `metric_failures` AND metrics are rubric/coverage gaps | Eval | Eval spec is incomplete |
| 5 | `metric_failures` AND metrics are reasoning/instruction-following | Prompt/Policy | Prompt quality problem |
| 6 | `metric_failures` AND metrics are latency/cost | Ops | Operational constraint violation |
| 7 | `tool_errors.count > 0` AND error type is logic/misuse | Prompt/Policy | Agent misusing tools |
| 8 | Compilation failure (schema inconsistency) | Architect | Spec is internally inconsistent |
| 9 | Compilation failure (missing contracts) | Tooling | ToolContract incomplete |
| 10 | No rule matches | Architect | Default: treat as design problem |

### 8.4 Ambiguity protocol
When multiple rules match (e.g., tool errors AND routing anomalies), classify by **highest priority rule** (lowest number). The routing trace must log all matching rules, not just the winner, so the pattern can be reviewed during meta-evaluation.

---

## 9) Promotion Protocol (Artifact Mutation)

### 9.1 Problem
The Optimizer (or other non-owning roles) may recommend changes to artifacts they don't own. This must be handled without violating ownership.

### 9.2 The `PromotionDecision` workflow

```
1. Proposer (e.g., Optimizer) produces a PromotionDecision artifact:
   - target_artifact: e.g., "SystemSpec"
   - proposed_changes: structured diff (not prose)
   - justification: metric evidence
   - expected_impact: predicted metric changes

2. Orchestrator receives PromotionDecision, routes to `apply_promotion` node.

3. `apply_promotion` dispatches to the OWNING lead of target_artifact:
   - Architect validates and applies changes to SystemSpec
   - Prompt/Policy validates and applies changes to PromptPack
   - etc.

4. Owning lead returns:
   - accepted: changes applied, new artifact version
   - rejected: reason (with structured justification)
   - modified: changes applied with modifications, explanation

5. If accepted/modified: gate re-run is triggered for affected gates.
6. If rejected: Orchestrator logs rejection and continues to next phase.
```

### 9.3 Rule
No artifact is ever mutated by a non-owner. PromotionDecision is a **request**, not a command.

---

## 10) Human Gate (Optional)

### 10.1 When it triggers
The `gate_human` node is activated when:
- The playbook explicitly requires it (configurable per playbook)
- A role subgraph flags `needs_human_review: true` in its output
- Budget is exhausted and the system needs human guidance
- The confidence score from a quality gate is in an ambiguous band (e.g., between 0.4 and 0.7)

### 10.2 Human gate interface
Input to human:
- Current artifact summaries (not full payloads)
- Gate results so far
- Specific questions or decision points flagged by the system
- Routing trace (why we're here)

Human can:
- Approve (continue to next phase)
- Reject with feedback (route to specified role)
- Override budget (increase caps)
- Terminate (finalize with current state)
- Inject constraints (added to ConstraintPack)

### 10.3 Default behavior
If no human is available (autonomous mode), `gate_human` auto-approves after logging the review request. The log must be inspectable after the fact.

---

## 11) State Broker (Context & Memory Management)

### 11.1 Problem
With 7+ role subgraphs and 3-5 workers each, passing full artifacts through graph state causes:
- Context window exhaustion in individual agents
- Serialization overhead on every state transition
- Stale reads when artifacts are updated mid-pipeline

### 11.2 Architecture
The State Broker is an infrastructure component (not an agent) that provides:

**Storage:**
- Artifacts stored by `(artifact_type, version)` key
- Full artifact payloads stored externally (not in graph state)
- Graph state carries only `artifact_ref: {type, version, summary_hash}`

**Access patterns:**
- `read_full(artifact_type)` → full artifact (for the owning lead or deep analysis)
- `read_summary(artifact_type)` → LLM-generated summary (for non-owners, workers)
- `read_section(artifact_type, section_path)` → specific section (for targeted reads)
- `write(artifact_type, new_value)` → validates ownership, increments version, updates summaries

**Summarization:**
- When an artifact is written, the State Broker generates a summary (bounded to ~500 tokens)
- Summaries are cached and invalidated on write
- Workers receive summaries by default; leads receive full artifacts for their owned types and summaries for others

### 11.3 History management
- `history` entries are structured: `{phase, decision, outcome, timestamp}`
- Max 50 entries in active history
- When exceeded, oldest 25 are compressed into a summary entry
- Full history always available in the State Broker for post-hoc analysis

---

## 12) Playbooks as Phase DAGs (Meta-level)

Playbooks are small DAGs executed by the Orchestrator.

### 12.1 Build (recommended default)
1. **Gather Constraints** → ConstraintPack
2. **Architect** → SystemSpec
3. **Prompt/Policy** → PromptPack
4. **Tooling** → ToolContract (+ mocks)
5. **Eval (smoke)** → ExperimentReport baseline
6. **Ops (instrument)** → TelemetrySpec + SLOReport
7. **Compile** → CompiledSpec (LangGraphSpec / DeepAgentSpec / HybridSpec)
8. **Human Gate** (optional, configurable)
9. **Finalize**

Allowed loops (bounded, max 3 iterations each):
- Eval fails → `classify_failure` → route to Prompt/Policy or Architect or Tooling
- Ops fails → `classify_failure` → route to Tooling or Architect
- Compile fails → `classify_failure` → route to Architect or Tooling
- PromotionDecision pending → `apply_promotion` → re-run affected gate

### 12.2 Debug
1. **Gather Constraints** → ConstraintPack (focused on the bug report)
2. **Repro swarm** → BugReport
3. **Classify failure** → determine root cause role
4. **Patch** (Architect or Prompt/Policy or Tooling) → updated artifact(s)
5. **Eval regression** → pass/fail + failure clusters
6. **Compile** (if SystemSpec changed)
7. **Finalize**

### 12.3 Optimize
1. **Eval baseline** → ExperimentReport
2. **Optimizer** → ExperimentSpec
3. **Eval executes experiments** → ExperimentReport comparisons
4. **PromotionDecision** → `apply_promotion` → owning leads apply updates
5. **Ops check** → cost/latency gate
6. **Compile** (if SystemSpec changed) → updated CompiledSpec
7. **Human Gate** (optional)
8. **Finalize**

### 12.4 Playbook metadata (required)
Each playbook must define:
- Phase list with ordering constraints
- Required artifacts at entry (preconditions)
- Required gates at each phase exit
- Allowed bounded loops with max iteration counts
- Termination conditions (success, failure, budget exhaustion)
- Human gate placement (required / optional / skip)

---

## 13) Sub-agent Policy (Bounded Swarms)

Role subgraphs may spawn workers, but must enforce:
- `max_spawns_per_role` (see §14 for defaults)
- `max_steps_per_worker`
- `max_tool_calls_per_worker`
- Early stop when confidence is high
- Structured outputs only (no decision authority)
- Workers access artifacts via State Broker summaries, not full payloads

---

## 14) Budget Profiles (Concrete)

### 14.1 Standard Build Profile

**Global budget:**
- `max_steps`: 100
- `max_tokens`: 500,000
- `max_tool_calls`: 200
- `max_spawns`: 30

**Per-role allocations:**

| Role | max_steps | max_tokens | max_tool_calls | max_spawns |
|---|---|---|---|---|
| Architect | 15 | 80,000 | 30 | 5 |
| Prompt/Policy | 10 | 60,000 | 20 | 4 |
| Tooling | 10 | 40,000 | 30 | 3 |
| Eval | 20 | 100,000 | 50 | 5 |
| Optimizer | 15 | 80,000 | 30 | 5 |
| Ops | 8 | 30,000 | 15 | 2 |
| Compiler | 10 | 60,000 | 15 | 3 |
| Orchestrator (overhead) | 12 | 50,000 | 10 | 0 |

These are starting points. Adjust based on task complexity.

### 14.2 Budget exhaustion protocol
When a role exhausts any budget dimension:
1. Role subgraph returns `status: budget_exhausted` with current progress and remaining work estimate.
2. Orchestrator evaluates: is the partial output usable?
   - If yes: proceed with partial artifact, log warning.
   - If no: check global budget for reallocation headroom.
3. If reallocation possible (other roles underspent): reallocate up to 50% of underspent budget.
4. If reallocation not possible: trigger `gate_human` with budget exhaustion context.
5. If autonomous mode: finalize with best-effort output and `status: partial`.

---

## 15) Meta-Evaluation

### 15.1 Purpose
Evaluate the meta-system itself, not just the systems it designs.

### 15.2 Tracked metrics
- **Route accuracy**: when failures loop (same failure type recurs after fix attempt), log the misroute
- **Budget utilization**: actual spend vs allocation per role, per playbook type
- **Gate signal quality**: false positive rate (gate passes but downstream fails) and false negative rate (gate fails but fix was unnecessary)
- **Loop count distribution**: how many retry loops per playbook run; high counts indicate systematic issues
- **Time-to-compile**: phases before first successful compile; high counts indicate spec quality issues
- **Promotion acceptance rate**: accepted vs rejected PromotionDecisions; low acceptance indicates misalignment

### 15.3 Collection
These metrics are logged automatically by the Orchestrator into a `MetaEvalLog` (append-only, not gated). Periodic human review of MetaEvalLog drives improvements to the failure taxonomy, budget profiles, and playbook design.

---

## 16) Implementation Order (Practical)

1. Define JSON schemas for all artifacts (SystemSpec with runtime extensions, PromptPack, EvalSpec, ToolContract, ExperimentReport, ConstraintPack, PromotionDecision, CompiledSpec)
2. Implement State Broker (artifact storage, access control, summarization)
3. Implement Meta Orchestrator graph + playbook runner + budget enforcement
4. Implement `classify_failure` node with initial rule set
5. Implement ArchitectSubgraph to produce valid SystemSpec
6. Implement EvalSubgraph for smoke/regression scoring
7. Implement `gather_constraints` node
8. Add Prompt/Policy and Tooling subgraphs
9. Add Optimizer subgraph + PromotionDecision protocol
10. Add Ops subgraph + production gate
11. Add Compiler subgraph (with validation)
12. Add Human Gate (optional, can be stubbed earlier)
13. Add meta-evaluation logging
14. Tune budget profiles based on initial runs
