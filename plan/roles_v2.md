# Roles & Responsibilities v2 (Runtime-Agnostic: LangGraph + DeepAgents + Hybrid)

This document defines the **lead roles** in the specialist team and how they collaborate via **artifact-driven handoffs**.
All roles must support building systems targeting:
- **LangGraph**
- **DeepAgents**
- **Hybrid**

---

## 0) Operating Principles

### 0.1 Leads Decide, Workers Assist
- **Leads** make decisions, own artifacts, and sign off.
- **Sub-agents (workers)** can research, draft, test, and summarize, but cannot finalize decisions or update artifacts.
- Each lead has an explicit **budget cap** (steps/tokens/tool calls/spawns).

### 0.2 Ownership Is Exclusive
- Each artifact has exactly one owning lead.
- Non-owners have read-only access (via State Broker summaries by default).
- Cross-artifact changes go through the **Promotion Protocol** — never direct writes.

### 0.3 Structured Outputs Only
- Every lead and worker must return structured artifacts, not prose.
- Gate inputs and routing decisions depend on structured fields, not natural language parsing.

---

## 1) Orchestrator (Deep, but Bounded)

### Purpose
Central routing, budgeting, sequencing, and termination. The Orchestrator is the only role that sees the full pipeline state and makes sequencing decisions.

### Owns
- `ConstraintPack` (produced by gather_constraints)
- `MetaEvalLog` (append-only)
- Playbook selection and phase DAG execution
- Budget allocation, enforcement, and reallocation
- Routing trace

### Produces / Updates
- `routing_trace` (why each routing decision was made)
- `history` (bounded decision log)
- `status` (running | blocked | awaiting_human | done | failed)
- Phase scheduling decisions
- Budget consumption records

### Key Responsibilities
- Run `gather_constraints` before first phase to collect cross-role context
- Run `classify_failure` using structured heuristics (not LLM judgment)
- Execute the Promotion Protocol when PromotionDecisions are pending
- Track and log meta-evaluation metrics
- Enforce loop caps and budget exhaustion protocol

### Must Not
- Write SystemSpec / PromptPack / ToolContract / EvalSpec / CompiledSpec directly
- Classify failures using unstructured LLM reasoning
- Override gate decisions (can escalate to human gate)
- Apply PromotionDecisions directly (must route to owning lead)

---

## 2) Systems Architect (Fully Deep)

> Formerly "LangGraph Architect," expanded to be runtime-agnostic.

### Purpose
Design the **SystemSpec**: topology, state, routing, failure handling, and boundaries. The Architect is responsible for the structural soundness of the designed system.

### Owns
- `SystemSpec` (source of truth — core + runtime extensions)

### Reads
- `ConstraintPack` (eval, tool, ops, and user constraints)
- `EvalSpec` (to understand what will be tested)
- `ToolContract` (to understand available tool interfaces)
- `PromotionDecision` (when the Architect is asked to apply proposed changes)

### Runtime Guidance

**LangGraph:**
- Node/edge topology, conditional routing, state reducers
- State discipline: typed keys, explicit reads/writes per node
- Checkpointer configuration and interrupt points
- Tool node placement and retry wrappers

**DeepAgents:**
- Planner/worker/critic structure and role definitions
- Recursion rules: max depth, replanning triggers
- Spawn policies: max breadth, termination heuristics
- Escalation rules: when workers escalate to planner

**Hybrid:**
- Boundary map: which components are graph-managed vs recursion-managed
- Boundary contracts: input/output schemas, state ownership at each boundary
- Failure propagation: how errors cross the graph/recursion boundary
- Shared state protocol: what state is shared vs isolated, merge strategies
- Decision framework: graph for enumerable paths, recursion for open-ended reasoning

### Responds to Promotion Protocol
When a PromotionDecision targets SystemSpec:
- Evaluates proposed changes against architectural constraints
- Accepts, rejects (with structured justification), or modifies
- Increments SystemSpec version on acceptance

### Typical Worker Sub-agents
- Topology proposer
- State schema reviewer
- Failure-mode reviewer
- Hybrid boundary analyst

---

## 3) Evaluation Lead (Fully Deep)

### Purpose
Define and measure "good." Provides the **quality gate** and regression protection. The Eval lead is the system's primary feedback mechanism.

### Owns
- `EvalSpec` (datasets, metrics, thresholds, rubrics)
- `ExperimentReport` (scores, failure clusters, comparisons)

### Reads
- `SystemSpec`, `PromptPack`, `ToolContract` (to understand what's being evaluated)
- `ConstraintPack` (to align metrics with user/ops constraints)
- `CompiledSpec` (to evaluate the compiled output, not just the abstract design)

### Produces for Gates
- `quality_gate_output`:
  - `pass`: bool
  - `score`: float (0.0–1.0)
  - `failure_clusters[]`: grouped failure descriptions
  - `failure_signals`: structured data for classify_failure
  - `recommended_fix_route`: suggestion (non-binding)

### Runtime Guidance

**LangGraph:**
- Path correctness: are all valid paths reachable? Do conditional edges route correctly?
- State mutation integrity: do reducers produce expected results?
- Tool call correctness: right tool, right args, right error handling
- Dead-end detection: are there nodes with no outbound edges that aren't terminal?

**DeepAgents:**
- Plan coherence: does the planner produce actionable, non-circular plans?
- Loop stability: do critic loops converge or oscillate?
- Spawn control: are spawn limits respected? Do workers terminate?
- Escalation correctness: do workers escalate at the right times?
- Self-repair success rate: when the critic rejects, does the next iteration improve?

**Hybrid:**
- Boundary failures: do inputs/outputs match boundary contracts?
- Handoff correctness: is state preserved across the graph/recursion boundary?
- Distributed tracing: can a failure be traced across both zones?
- Mode transition: does the system correctly enter and exit recursion zones?

### Typical Worker Sub-agents
- Adversarial case generator
- Rubric writer
- Failure clustering analyst
- Regression suite runner

---

## 4) Optimization Lead (Fully Deep)

### Purpose
Run systematic improvement via experiments; propose changes backed by metrics. The Optimizer never directly mutates artifacts it doesn't own — it proposes changes via PromotionDecision.

### Owns
- `ExperimentSpec` (experiment plan: what to vary, what to measure, what to hold constant)
- `PromotionDecision` (proposed changes + evidence)

### Reads
- All artifacts (read-only, via State Broker summaries for most, full for ExperimentReport)

### Produces
- `ExperimentSpec`: defines experiments before execution
- `PromotionDecision`: after experiments complete, proposes specific changes to target artifacts

### Does NOT Do
- Directly modify SystemSpec, PromptPack, ToolContract, or any artifact it doesn't own
- Apply its own recommendations — the owning lead does that via Promotion Protocol

### Runtime Guidance

**LangGraph:**
- Routing thresholds (adjust conditional edge parameters)
- Retry/caching policies (per tool node)
- State pruning (remove unused state keys to reduce overhead)
- Model-per-node selection (different models for different complexity levels)

**DeepAgents:**
- Reflection depth (how many critic iterations before accepting)
- Spawn limits (trade breadth for depth or vice versa)
- Termination heuristics (confidence thresholds, diminishing-returns detection)
- Planner granularity (coarse plans with autonomous workers vs fine-grained step-by-step)

**Hybrid:**
- Boundary placement (move components between graph and recursion zones)
- Caching boundaries (where to cache across the boundary)
- Model allocation (which models for graph nodes vs recursion agents)
- Budget distribution across zones

### Typical Worker Sub-agents
- Ablation designer
- Results analyst
- Cost/performance tradeoff analyst

---

## 5) Prompt & Policy Engineer (Semi-deep → Deep)

### Purpose
Author prompts and policies that drive consistent tool use and safe behavior. The Prompt/Policy lead is responsible for the "intelligence layer" — what the agents actually say and do.

### Owns
- `PromptPack` (system prompts, role prompts, tool-call patterns, guardrails, few-shot examples)

### Reads
- `SystemSpec` (to understand the topology and state model prompts must respect)
- `ToolContract` (to align prompt tool-call patterns with actual tool schemas)
- `ConstraintPack` (safety and behavioral constraints from user/ops)
- `ExperimentReport` (to understand what's failing and why)

### Responds to Promotion Protocol
When a PromotionDecision targets PromptPack:
- Evaluates proposed changes against safety constraints and prompt coherence
- Accepts, rejects (with structured justification), or modifies

### Runtime Guidance

**LangGraph:**
- Per-node prompts aligned with node's state reads/writes
- Tool call formatting matching ToolContract schemas
- State update instructions (what to write, what to leave alone)
- Conditional routing hints (how to signal routing decisions in output)

**DeepAgents:**
- Planner prompt: how to decompose tasks, when to spawn workers, when to stop
- Critic prompt: acceptance criteria, how to provide actionable feedback
- Worker prompt: scope boundaries, escalation triggers
- Self-correction templates: how to incorporate critic feedback

**Hybrid:**
- Boundary prompts: how agents behave differently in graph vs recursion zones
- Shared conventions for artifact/state ownership references
- Handoff instructions: what context to pass across boundaries

### Typical Worker Sub-agents
- Prompt variant generator
- Policy test writer
- Jailbreak/edge-case prober (benign red-team)

---

## 6) Tooling & Integrations Lead (Semi-deep)

### Purpose
Define reliable tool interfaces and integration patterns; reduce flakiness. The Tooling lead ensures that every tool call in the system has a well-defined contract.

### Owns
- `ToolContract` (schemas, retries, idempotency, caching, auth patterns, rate limit policies)
- Mock adapters / test doubles (if implemented in codebase)

### Reads
- `SystemSpec` (to understand which components use which tools)
- `ConstraintPack` (tool availability and known issues)

### Responds to Promotion Protocol
When a PromotionDecision targets ToolContract:
- Evaluates proposed changes against reliability requirements
- Accepts, rejects (with structured justification), or modifies

### Runtime Guidance

**LangGraph:**
- Tool nodes/wrappers: each tool call is a node with defined input/output schemas
- Deterministic retries: retry policy per tool (max retries, backoff, fallback)
- Caching policy: which tool calls are cacheable, TTL, invalidation

**DeepAgents:**
- Tool-call gating during loops: which tools workers can call vs require planner approval
- Sandboxing: tool calls in recursion zones must be idempotent or explicitly flagged as side-effecting
- Recursion-safe rate limiting: rate limits that account for spawned workers

**Hybrid:**
- Shared tool abstractions: same tool contract used by both graph and recursion zones
- Boundary-safe tool usage: tools that cross zone boundaries need explicit contracts
- Tool ownership: which zone "owns" each tool (affects retry and caching strategy)

### Typical Worker Sub-agents
- Schema validator
- Adapter generator
- Tool reliability tester

---

## 7) Compiler Lead (NEW)

### Purpose
Convert the abstract SystemSpec into a runtime-specific CompiledSpec. The Compiler is the bridge between design and implementation.

### Owns
- `CompiledSpec` (LangGraphSpec, DeepAgentSpec, or HybridSpec depending on runtime_target)
- `CompilationReport` (warnings, assumptions made, ambiguities resolved)

### Reads
- `SystemSpec` (primary input)
- `PromptPack` (to embed prompts into compiled output where applicable)
- `ToolContract` (to generate tool wrappers/nodes)

### Key Responsibilities
- Validate SystemSpec for internal consistency during compilation
- Generate structured config + code stubs for the target runtime
- Report all assumptions, ambiguities, and warnings
- Flag compilation failures with structured error types for the failure classifier

### Compilation by Runtime

**LangGraph output:**
- Node definitions with signatures (inputs, outputs, state reads/writes)
- Edge list (static + conditional with condition function signatures)
- State type definition with reducer map
- Tool node wrappers with retry/caching config from ToolContract
- Checkpointer configuration
- Code stubs annotated with `# STUB: implement` markers

**DeepAgents output:**
- Planner/worker/critic role definitions with embedded prompts
- Loop configuration (max iterations, termination conditions, convergence criteria)
- Spawn policies (max depth, max breadth, budget per spawn)
- Escalation rules and reflection boundaries
- Termination heuristics

**Hybrid output:**
- Component classification (graph-managed vs recursion-managed)
- Boundary adapter definitions with input/output contracts
- State synchronization protocol (shared keys, merge strategies)
- Cross-boundary failure handling rules
- Shared telemetry configuration

### Validation Checks
During compilation, the Compiler enforces:
- No undefined artifact handoffs between components
- No unbounded loops without loop breakers
- All tool calls covered by a ToolContract entry
- Budget defaults present for each component
- State schema consistency (no reads of unwritten keys)
- Boundary contracts complete for hybrid targets (both sides defined)
- Prompt coverage (every component that needs a prompt has one in PromptPack)

### Failure Types (for classify_failure)
- `schema_inconsistency`: SystemSpec has internal contradictions
- `missing_contract`: tool call without ToolContract entry
- `unbounded_recursion`: recursion with no termination guarantee
- `boundary_mismatch`: hybrid boundary contract has mismatched types or missing side
- `prompt_gap`: component requires prompt not in PromptPack

### Typical Worker Sub-agents
- Code stub generator
- Validation checker
- Boundary adapter generator

---

## 8) Reliability / Ops Lead (Thin Enforcement Agent)

### Purpose
Production stability and enforcement: cost/latency/reliability budgets, telemetry, fallbacks. Ops measures both the **meta-system's** operational characteristics and the **projected** characteristics of designed systems.

### Owns
- `TelemetrySpec` (what to log, metric definitions, sampling rates)
- `SLOReport` (production gate results)

### Reads
- `SystemSpec` (to understand what needs monitoring)
- `ToolContract` (to understand tool reliability characteristics)
- `CompiledSpec` (to validate operational feasibility of compiled output)

### Produces for Gates
- `production_gate_output`:
  - `pass`: bool
  - `violations[]`: `{metric, threshold, actual, severity}`
  - `failure_signals`: structured data for classify_failure
  - `recommended_fix_route`: suggestion (non-binding)

### What Ops Measures

**For the designed system (projected):**
- Estimated token cost per request (based on component count, model assignments, expected path lengths)
- Estimated latency (based on sequential depth of component graph)
- Tool reliability budget (based on ToolContract retry policies and expected failure rates)
- Spawn budget feasibility (based on recursion depth and breadth policies)

**For the meta-system (actual, logged to MetaEvalLog):**
- Actual token consumption per phase
- Actual latency per phase
- Budget utilization efficiency

### Runtime Guidance

**LangGraph:**
- Cycle detection: are there cycles without explicit breakers?
- Dead-end detection: terminal nodes that aren't marked as terminal
- State growth monitoring: keys that grow unboundedly

**DeepAgents:**
- Recursion depth limits: projected worst-case depth
- Spawn caps: projected worst-case total spawns
- Loop breakers: every loop has a termination condition
- Timeout rules: per-agent and per-loop timeouts

**Hybrid:**
- Cross-component tracing: can a request be traced across both zones?
- Boundary failure containment: does a failure in one zone stay contained?
- Resource allocation: is budget split between zones reasonable?

### Design Constraint
This role should remain **thin** (deterministic policy + analysis), not exploratory. Ops does not design — it validates and measures.

### Typical Worker Sub-agents
- Cost estimator (rule-based, not exploratory)
- Latency modeler (based on topology analysis)

---

## 9) Data / Domain Curator (Optional, Semi-deep)

### Purpose
Curate and generate data to power evaluation and improve robustness.

### Owns
- Datasets (gold, edge cases, adversarial, synthetic)
- Domain packs and scenario libraries (consumed by EvalSpec)

### Reads
- `EvalSpec` (to understand what data is needed)
- `SystemSpec` (to understand what scenarios the system handles)
- `ExperimentReport` (to identify data gaps from failure clusters)

### Typical Worker Sub-agents
- Scenario generator
- Data labeler (rule-based where possible)
- Coverage analyst

---

## 10) Role Interaction Summary

### 10.1 Depth Strategy

| Role | Depth | Rationale |
|---|---|---|
| Architect | Fully deep | Design is exploratory, needs multiple perspectives |
| Eval | Fully deep | Thorough evaluation requires adversarial thinking |
| Optimizer | Fully deep | Experiments require design + analysis |
| Prompt/Policy | Semi-deep → Deep | Prompt engineering benefits from iteration |
| Tooling | Semi-deep | Contract definition is more structured than exploratory |
| Compiler | Semi-deep | Compilation is largely mechanical with validation |
| Ops | Thin | Deterministic analysis, not exploration |
| Data Curator | Semi-deep (optional) | Data generation benefits from some exploration |
| Orchestrator | Deep but bounded | Routing is complex but must be disciplined |

### 10.2 Communication Model
- Roles do NOT communicate directly with each other.
- All communication goes through **artifacts** mediated by the **State Broker** and sequenced by the **Orchestrator**.
- When a role needs input from another role's artifact, it reads it (via State Broker, typically as a summary).
- When a role wants to change another role's artifact, it creates a **PromotionDecision**.

### 10.3 Artifact Flow (Build Playbook)
```
ConstraintPack ──→ Architect ──→ SystemSpec
                                    │
                                    ├──→ Prompt/Policy ──→ PromptPack
                                    ├──→ Tooling ──→ ToolContract
                                    │
                                    ▼
                              Eval ──→ EvalSpec + ExperimentReport
                                    │
                                    ▼
                              Ops ──→ TelemetrySpec + SLOReport
                                    │
                                    ▼
                              Compiler ──→ CompiledSpec + CompilationReport
```

Feedback loops (bounded):
```
ExperimentReport failures ──→ classify_failure ──→ re-route to owning role
PromotionDecision ──→ apply_promotion ──→ owning lead validates ──→ re-gate
```
