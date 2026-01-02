# Architecture Documentation

This document provides a detailed technical analysis of the GIA Agentic Research Pipeline architecture.

---

## Table of Contents

1. [System Overview](#1-system-overview)
2. [Data Flow Architecture](#2-data-flow-architecture)
3. [Agent System](#3-agent-system)
4. [Orchestration Layer](#4-orchestration-layer)
5. [Storage Architecture](#5-storage-architecture)
6. [Gate System](#6-gate-system)
7. [Evidence and Citation System](#7-evidence-and-citation-system)
8. [Graceful Degradation](#8-graceful-degradation)
9. [Observability](#9-observability)
10. [Extension Points](#10-extension-points)

---

## 1. System Overview

### 1.1 Design Philosophy

The GIA pipeline follows several core architectural principles:

| Principle | Description |
|-----------|-------------|
| **Filesystem-First** | All outputs written as durable artifacts (Markdown, JSON, LaTeX) to project folders |
| **Schema-Driven** | JSON schemas as contracts between components |
| **Gate-Based Quality** | Explicit gates that PASS, DOWNGRADE, or BLOCK based on prerequisites |
| **Graceful Degradation** | Pipeline continues with scaffold outputs when optional components fail |
| **Auditability** | Every claim must have traceable support; provenance is preserved |

### 1.2 High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           UNIFIED PIPELINE RUNNER                            │
│                         (src/pipeline/runner.py)                             │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌──────────────┐   ┌──────────────┐   ┌──────────────┐   ┌──────────────┐ │
│  │   Phase 1    │──▶│   Phase 2    │──▶│   Phase 3    │──▶│   Phase 4    │ │
│  │   Intake     │   │  Literature  │   │     Gap      │   │   Writing    │ │
│  │  & Analysis  │   │  & Planning  │   │  Resolution  │   │  & Review    │ │
│  └──────────────┘   └──────────────┘   └──────────────┘   └──────────────┘ │
│         │                  │                  │                  │          │
│         ▼                  ▼                  ▼                  ▼          │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                      WORKFLOW CACHE                                  │   │
│  │                 (.workflow_cache/*.json)                             │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                              │
├─────────────────────────────────────────────────────────────────────────────┤
│                           AGENT ORCHESTRATOR                                 │
│                        (src/agents/orchestrator.py)                          │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌────────────┐  ┌────────────┐  ┌────────────┐  ┌────────────┐           │
│  │   Agent    │  │   Agent    │  │   Agent    │  │   Agent    │    ...    │
│  │   A01-A04  │  │   A05-A09  │  │   A10-A15  │  │   A16-A25  │           │
│  └────────────┘  └────────────┘  └────────────┘  └────────────┘           │
│                                                                              │
├─────────────────────────────────────────────────────────────────────────────┤
│                              LLM LAYER                                       │
│                      (src/llm/claude_client.py)                              │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐             │
│  │   Claude Opus   │  │  Claude Sonnet  │  │  Claude Haiku   │             │
│  │   (Reasoning)   │  │    (Default)    │  │  (High-Volume)  │             │
│  └─────────────────┘  └─────────────────┘  └─────────────────┘             │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 1.3 Component Layers

| Layer | Location | Responsibility |
|-------|----------|----------------|
| **Pipeline Runner** | `src/pipeline/runner.py` | Chains phases, manages context, writes degradation summaries |
| **Workflow Orchestrators** | `src/agents/workflow.py`, `literature_workflow.py`, `gap_resolution_workflow.py` | Phase-specific agent sequencing |
| **Agent Orchestrator** | `src/agents/orchestrator.py` | Inter-agent calls, revision loops, convergence detection |
| **Base Agents** | `src/agents/base.py` | Common agent functionality, Claude API integration |
| **Agent Registry** | `src/agents/registry.py` | Agent discovery, capabilities, permissions |
| **LLM Client** | `src/llm/claude_client.py` | Multi-model support, task-based selection, caching |
| **Gates** | `src/citations/gates.py`, `src/claims/gates.py`, etc. | Quality enforcement checkpoints |
| **Storage** | `src/evidence/store.py`, `src/citations/registry.py` | Filesystem-based data persistence |

---

## 2. Data Flow Architecture

### 2.1 Project Folder Structure

Each research project uses a standardized folder layout:

```
project_folder/
├── project.json                    # Project metadata and configuration
├── data/                           # User-provided data files
│   ├── *.csv, *.xlsx, *.json      # Data files for analysis
│   └── analysis_scripts/          # User analysis scripts
├── outputs/                        # Pipeline-generated outputs
│   ├── RESEARCH_OVERVIEW.md       # Phase 1 output
│   ├── LITERATURE_REVIEW.md       # Phase 2 output
│   ├── PROJECT_PLAN.md            # Planning output
│   ├── metrics.json               # Computed analysis metrics
│   ├── artifacts.json             # Analysis provenance
│   ├── degradation_summary.json   # Degradation events log
│   └── deliberation.json          # Multi-agent consensus records
├── sources/                        # Evidence sources
│   └── {source_id}/
│       ├── raw/                   # Original source files
│       ├── parsed.json            # Parsed content
│       └── evidence.json          # Extracted evidence items
├── bibliography/
│   ├── citations.json             # Citation registry
│   └── references.bib             # BibTeX references
├── claims/
│   └── claims.json                # Claim records with evidence links
├── paper/                          # LaTeX paper sections
│   ├── main.tex                   # Main document
│   ├── introduction.tex
│   ├── methods.tex
│   ├── results.tex
│   └── ...
└── .workflow_cache/                # Stage result cache
    ├── data_analyst.json
    ├── research_explorer.json
    └── ...
```

### 2.2 Artifact Flow Between Phases

```
Phase 1 (Intake)                    Phase 2 (Literature)
┌─────────────────┐                 ┌─────────────────┐
│  project.json   │────────────────▶│ RESEARCH_       │
│  data/*         │                 │ OVERVIEW.md     │
└─────────────────┘                 └────────┬────────┘
        │                                    │
        ▼                                    ▼
┌─────────────────┐                 ┌─────────────────┐
│ Data Analysis   │                 │ Hypothesis      │
│ Gap Analysis    │                 │ Literature      │
│ Overview Gen    │                 │ Paper Structure │
└─────────────────┘                 └────────┬────────┘
                                             │
                                             ▼
Phase 3 (Gap Resolution)            Phase 4 (Writing)
┌─────────────────┐                 ┌─────────────────┐
│ Gap Resolver    │────────────────▶│ Section Writers │
│ Analysis Exec   │                 │ Referee Review  │
│ Metrics Output  │                 │ Paper Assembly  │
└─────────────────┘                 └─────────────────┘
```

### 2.3 Inter-Component Data Contracts

All data exchange follows JSON Schema contracts in `src/schemas/`:

| Schema | Purpose |
|--------|---------|
| `evidence_item.schema.json` | Evidence extracted from sources with locators |
| `citation_record.schema.json` | Bibliographic records with verification status |
| `claim_record.schema.json` | Claims linked to evidence and metrics |
| `metric_record.schema.json` | Computed analysis metrics with provenance |
| `agent_message.schema.json` | Inter-agent communication protocol |
| `degradation_event.schema.json` | Graceful degradation event records |
| `degradation_summary.schema.json` | Pipeline degradation summary |
| `task_decomposition.schema.json` | Task breakdown for orchestration |

---

## 3. Agent System

### 3.1 Agent Hierarchy

```
                         ┌─────────────────┐
                         │   BaseAgent     │
                         │  (src/agents/   │
                         │    base.py)     │
                         └────────┬────────┘
                                  │
          ┌───────────────────────┼───────────────────────┐
          │                       │                       │
          ▼                       ▼                       ▼
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│  Phase 1 Agents │     │  Phase 2 Agents │     │  Quality Agents │
│  A01-A04        │     │  A05-A09        │     │  A12-A15        │
│  - DataAnalyst  │     │  - Hypothesis   │     │  - Critical     │
│  - Research     │     │  - Literature   │     │    Review       │
│  - Gap          │     │  - Synthesis    │     │  - Style        │
│  - Overview     │     │  - Structure    │     │  - Consistency  │
└─────────────────┘     └─────────────────┘     └─────────────────┘
```

### 3.2 BaseAgent Architecture

The `BaseAgent` class (`src/agents/base.py`) provides:

```python
class BaseAgent(ABC):
    """
    Features automatically included:
    - Current date context (models know today's date)
    - Web search awareness (models flag when they need current info)
    - Optimal model selection based on task type
    - Prompt caching with configurable TTL
    - Critical rules enforcement
    - Iterative refinement with revision support
    - Quality self-assessment
    """

    # Core methods
    async def execute(context: dict) -> AgentResult    # Main execution
    async def revise(result, feedback) -> AgentResult  # Revision loop
    async def self_critique(result) -> dict            # Quality assessment

    # Internal helpers
    async def _call_claude(message) -> tuple[str, int] # LLM API call
    def _build_result(...) -> AgentResult              # Result construction
```

### 3.3 Agent Registry

All agents register in `src/agents/registry.py` with `AgentSpec`:

```python
@dataclass
class AgentSpec:
    id: str                              # Unique ID (A01, A02, etc.)
    name: str                            # Human-readable name
    class_name: str                      # Python class name
    module_path: str                     # Module path for import
    model_tier: ModelTier                # Which model tier it uses
    capabilities: List[AgentCapability]  # What it can do
    input_schema: AgentInputSchema       # What it needs
    output_schema: AgentOutputSchema     # What it produces
    can_call: List[str]                  # Agent IDs it can invoke
    max_iterations: int                  # Max self-revision iterations
    supports_revision: bool              # Whether it can revise its output
    uses_extended_thinking: bool         # Whether it uses thinking mode
```

### 3.4 Agent Capabilities

Agents declare capabilities used for discovery and routing:

| Capability | Description |
|------------|-------------|
| `DATA_ANALYSIS` | Analyze data files and generate statistics |
| `DATA_VALIDATION` | Validate data quality and integrity |
| `CODE_EXECUTION` | Execute generated code in sandbox |
| `HYPOTHESIS_DEVELOPMENT` | Formulate testable hypotheses |
| `LITERATURE_SEARCH` | Search and retrieve literature |
| `LITERATURE_SYNTHESIS` | Synthesize literature findings |
| `DOCUMENT_GENERATION` | Generate structured documents |
| `CRITICAL_REVIEW` | Review outputs for quality |
| `STYLE_ENFORCEMENT` | Enforce writing style rules |
| `CONSISTENCY_CHECK` | Cross-document consistency validation |

### 3.5 Model Selection

Task-based automatic model selection:

| Task Type | Model | Use Case |
|-----------|-------|----------|
| `COMPLEX_REASONING` | Opus | Research synthesis, scientific analysis |
| `SCIENTIFIC_ANALYSIS` | Opus | Complex analytical tasks |
| `ACADEMIC_WRITING` | Opus | Academic paper writing |
| `CODING` | Sonnet | Code generation, agents |
| `AGENTIC_WORKFLOW` | Sonnet | Multi-step agent tasks |
| `DATA_ANALYSIS` | Sonnet | Data processing, analysis |
| `CLASSIFICATION` | Haiku | High-volume classification |
| `SUMMARIZATION` | Haiku | Document summarization |
| `EXTRACTION` | Haiku | Data extraction tasks |

---

## 4. Orchestration Layer

### 4.1 Execution Modes

The `AgentOrchestrator` (`src/agents/orchestrator.py`) supports three execution modes:

```python
class ExecutionMode(Enum):
    SINGLE_PASS = "single_pass"     # Run once, no review
    WITH_REVIEW = "with_review"     # Run + critical review
    ITERATIVE = "iterative"         # Run + review + revise until converged
```

### 4.2 Orchestrator Flow

```
                    ┌─────────────────┐
                    │  execute_agent  │
                    └────────┬────────┘
                             │
                    ┌────────▼────────┐
                    │  Check Cache    │
                    │  (if enabled)   │
                    └────────┬────────┘
                             │
              ┌──────────────┴──────────────┐
              │                             │
         Cache Hit                     Cache Miss
              │                             │
              ▼                             ▼
     ┌────────────────┐           ┌────────────────┐
     │  Return Cached │           │  Run Agent     │
     │     Result     │           │  Execute()     │
     └────────────────┘           └────────┬───────┘
                                           │
                                  ┌────────▼────────┐
                                  │  Self-Critique  │
                                  │  (if enabled)   │
                                  └────────┬────────┘
                                           │
                        ┌──────────────────┴───────────────────┐
                        │                                      │
                   Score > threshold                    Score < threshold
                        │                                      │
                        ▼                                      ▼
               ┌────────────────┐                    ┌────────────────┐
               │  Skip Review   │                    │ Critical Review│
               └────────┬───────┘                    └────────┬───────┘
                        │                                      │
                        └──────────────────┬───────────────────┘
                                           │
                                  ┌────────▼────────┐
                                  │  Convergence    │
                                  │  Check          │
                                  └────────┬────────┘
                                           │
                        ┌──────────────────┴───────────────────┐
                        │                                      │
                   Converged                             Not Converged
                        │                                      │
                        ▼                                      ▼
               ┌────────────────┐                    ┌────────────────┐
               │  Cache Result  │                    │  Revise Agent  │
               │  Return        │                    │  (loop back)   │
               └────────────────┘                    └────────────────┘
```

### 4.3 Inter-Agent Communication Protocol

Agents communicate via structured messages validated against `agent_message.schema.json`:

```python
# Request message
{
    "type": "request",
    "call_id": "uuid",
    "timestamp": "2026-01-02T12:00:00Z",
    "caller_agent_id": "A05",
    "target_agent_id": "A12",
    "reason": "Need critical review of hypothesis",
    "context": {...},
    "priority": "normal",
    "timeout_seconds": 600
}

# Response message
{
    "type": "response",
    "call_id": "uuid",
    "timestamp": "2026-01-02T12:05:00Z",
    "success": true,
    "result": {...},
    "execution_time": 45.2,
    "attempt": 1,
    "max_attempts": 2
}
```

### 4.4 Permission Enforcement

The orchestrator enforces inter-agent call permissions defined in `AgentSpec.can_call`:

```python
# Example: A05 can call A12 for critical review
"A05": AgentSpec(
    ...
    can_call=["A12"],  # HypothesisDeveloper can call CriticalReviewer
)
```

### 4.5 Convergence Detection

Revision loops terminate when convergence criteria are met:

```python
@dataclass
class ConvergenceCriteria:
    min_quality_score: float = 0.8      # Minimum quality threshold
    max_iterations: int = 3              # Maximum revision attempts
    score_improvement_threshold: float = 0.05  # Min improvement per iteration
    require_no_critical_issues: bool = True    # No critical issues allowed
```

### 4.6 Deliberation and Consensus

For complex decisions, multiple agents can deliberate:

```python
await orchestrator.execute_deliberation_and_consensus(
    agent_ids=["A12", "A13", "A14"],  # CriticalReview, StyleEnforcer, ConsistencyChecker
    context=context,
    consensus_threshold=0.7
)
# Writes outputs/deliberation.json with perspectives, conflicts, consolidated output
```

---

## 5. Storage Architecture

### 5.1 Workflow Cache

The `WorkflowCache` (`src/agents/cache.py`) enables resumable workflows:

```
.workflow_cache/
├── data_analyst.json           # Latest version
├── data_analyst_v1.json        # Version 1 (initial)
├── data_analyst_v2.json        # Version 2 (revision)
├── research_explorer.json
└── ...
```

Each cache entry contains:

```python
@dataclass
class CacheEntry:
    stage_name: str              # Workflow stage name
    timestamp: str               # When generated
    project_id: str              # Project identifier
    agent_result: dict           # Full AgentResult
    input_hash: str              # Hash of inputs (detect changes)
    version: int                 # 0=initial, 1+=revisions
    quality_score: float         # Quality if assessed
    feedback_summary: str        # What prompted this version
```

### 5.2 Evidence Store

The `EvidenceStore` (`src/evidence/store.py`) provides append-only JSONL storage:

```
.evidence/
└── evidence.jsonl              # Append-only ledger

sources/{source_id}/
├── raw/                        # Original source files
├── parsed.json                 # Parsed content
└── evidence.json               # Extracted evidence items
```

Key features:
- File locking to prevent concurrent write corruption
- Schema validation for all records
- Append-only for audit trail

### 5.3 Citation Registry

The `CitationRegistry` (`src/citations/registry.py`) manages bibliographic data:

```
bibliography/
├── citations.json              # Citation records
└── references.bib              # BibTeX export
```

Citation records are validated against `citation_record.schema.json`:

```json
{
    "citation_key": "fama1970",
    "title": "Efficient Capital Markets",
    "authors": ["Fama, Eugene F."],
    "year": 1970,
    "journal": "Journal of Finance",
    "verified": true,
    "source_id": "src_001",
    "created_at": "2026-01-02T12:00:00Z"
}
```

---

## 6. Gate System

### 6.1 Gate Architecture

Gates are quality checkpoints that enforce prerequisites before proceeding:

```
┌─────────────────┐
│   Input Data    │
└────────┬────────┘
         │
         ▼
┌─────────────────┐     ┌─────────────┐
│      Gate       │────▶│    PASS     │──▶ Continue normally
└────────┬────────┘     └─────────────┘
         │
         │              ┌─────────────┐
         ├─────────────▶│  DOWNGRADE  │──▶ Continue with warnings
         │              └─────────────┘
         │
         │              ┌─────────────┐
         └─────────────▶│    BLOCK    │──▶ Halt execution
                        └─────────────┘
```

### 6.2 Available Gates

| Gate | Location | Purpose |
|------|----------|---------|
| **Citation Gate** | `src/citations/gates.py` | Verify citation presence and formatting |
| **Citation Accuracy Gate** | `src/citations/verification_chain.py` | Verify citation accuracy against sources |
| **Literature Gate** | `src/literature/gates.py` | Check literature coverage requirements |
| **Evidence Gate** | `src/evidence/gates.py` | Validate evidence extraction quality |
| **Computation Gate** | `src/claims/gates.py` | Check claims against computed metrics |
| **Analysis Gate** | `src/analysis/gates.py` | Validate analysis script execution |

### 6.3 Gate Configuration

Gates can be configured via workflow context:

```python
context = {
    "computation_gate": {
        "enabled": True,
        "on_missing_metrics": "downgrade"  # or "block"
    },
    "citation_gate": {
        "enabled": True,
        "on_missing_citation": "downgrade"
    }
}
```

### 6.4 Gate Result Structure

```python
@dataclass
class GateResult:
    passed: bool                    # Whether gate passed
    action: Literal["pass", "downgrade", "block"]
    missing_items: List[str]        # What was missing
    warnings: List[str]             # Non-blocking issues
    recommendation: str             # Suggested action
```

---

## 7. Evidence and Citation System

### 7.1 Evidence Pipeline

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│  Source Fetch   │────▶│   PDF Parse     │────▶│    Evidence     │
│  (acquisition)  │     │   (pypdf)       │     │   Extraction    │
└─────────────────┘     └─────────────────┘     └────────┬────────┘
                                                         │
                                                         ▼
                                                ┌─────────────────┐
                                                │ Evidence Store  │
                                                │ (JSONL ledger)  │
                                                └─────────────────┘
```

### 7.2 Evidence Item Structure

```json
{
    "evidence_id": "ev_001",
    "source_id": "src_001",
    "claim_text": "The market exhibits mean reversion",
    "excerpt": "Our analysis shows significant mean reversion...",
    "locator": {
        "page": 12,
        "section": "Results"
    },
    "confidence": 0.85,
    "extracted_at": "2026-01-02T12:00:00Z"
}
```

### 7.3 Citation Verification Chain

```
┌─────────────────┐
│  Citation Key   │
└────────┬────────┘
         │
         ▼
┌─────────────────┐     ┌─────────────────┐
│ Local Registry  │────▶│    CrossRef     │
│ (citations.json)│     │   Resolver      │
└─────────────────┘     └────────┬────────┘
                                 │
                        ┌────────▼────────┐
                        │   OpenAlex      │
                        │   Resolver      │
                        └────────┬────────┘
                                 │
                        ┌────────▼────────┐
                        │ Semantic Scholar│
                        │   Resolver      │
                        └─────────────────┘
```

### 7.4 Source-Citation Mapping

The `source_citation_map` links sources to citations:

```python
# bibliography/source_citation_map.json
{
    "src_001": "fama1970",
    "src_002": "french1993"
}
```

---

## 8. Graceful Degradation

### 8.1 Degradation Protocol

When optional components fail, the pipeline continues with degraded operation:

```python
@dataclass
class DegradationEvent:
    stage: str                      # Which stage degraded
    reason_code: str                # Machine-readable reason
    message: str                    # Human-readable description
    severity: str                   # "warning" | "error" | "critical"
    recommended_action: str         # How to resolve
    details: Dict[str, Any]         # Additional context
    created_at: str                 # Timestamp
```

### 8.2 Degradation Patterns

| Pattern | Trigger | Result |
|---------|---------|--------|
| **Edison Fallback** | Edison API unavailable | Use Claude Literature Search |
| **Evidence Skip** | Source parsing fails | Continue without evidence |
| **Metric Scaffold** | Analysis script fails | Generate placeholder metrics |
| **Citation Downgrade** | Citation not verified | Mark as unverified, continue |

### 8.3 Degradation Summary

At pipeline completion, a summary is written to `outputs/degradation_summary.json`:

```json
{
    "schema_version": "1.0",
    "pipeline_run_id": "run_001",
    "created_at": "2026-01-02T12:00:00Z",
    "total_events": 2,
    "severity_counts": {
        "warning": 2,
        "error": 0,
        "critical": 0
    },
    "events": [...]
}
```

---

## 9. Observability

### 9.1 Tracing Architecture

OpenTelemetry tracing provides distributed observability:

```
┌─────────────────────────────────────────────────────────────────┐
│                        Pipeline Run                              │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │                    Phase 1 Span                          │   │
│  │  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐       │   │
│  │  │ Agent A01   │ │ Agent A02   │ │ Agent A04   │       │   │
│  │  │   Span      │ │   Span      │ │   Span      │       │   │
│  │  └─────────────┘ └─────────────┘ └─────────────┘       │   │
│  └─────────────────────────────────────────────────────────┘   │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │                    Phase 2 Span                          │   │
│  │  ...                                                     │   │
│  └─────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
                    ┌─────────────────┐
                    │  OTLP Exporter  │
                    └────────┬────────┘
                             │
                             ▼
                    ┌─────────────────┐
                    │  Trace Backend  │
                    │   (Jaeger/etc)  │
                    └─────────────────┘
```

### 9.2 Tracing Configuration

```python
# src/config.py
@dataclass(frozen=True)
class TracingConfig:
    SERVICE_NAME: str = "gia-research-agents"
    OTLP_ENDPOINT: str = os.getenv("OTLP_ENDPOINT", "http://localhost:4318/v1/traces")
    ENABLED: bool = os.getenv("ENABLE_TRACING", "false").lower() == "true"
```

### 9.3 Logging

Loguru is used throughout with structured logging:

```python
from loguru import logger

logger.info(f"Starting workflow for project {project_id}")
logger.warning(f"Cache miss for stage {stage_name}")
logger.error(f"Agent {agent_id} failed: {error}")
```

---

## 10. Extension Points

### 10.1 Adding New Agents

1. Create agent class inheriting from `BaseAgent`
2. Implement `async execute(context) -> AgentResult`
3. Register in `AGENT_REGISTRY` with `AgentSpec`
4. Add tests in `tests/test_<agent_name>.py`

### 10.2 Adding New Gates

1. Create gate function in appropriate module
2. Define configuration dataclass
3. Implement gate logic returning pass/downgrade/block
4. Add to workflow context configuration

### 10.3 Adding New Schemas

1. Create JSON Schema in `src/schemas/`
2. Add validation function in `src/utils/schema_validation.py`
3. Update components that produce/consume the schema

### 10.4 Adding New Workflows

1. Create workflow class in `src/agents/`
2. Define `WorkflowResult` dataclass
3. Implement agent sequencing logic
4. Integrate with unified pipeline runner

### 10.5 External API Integration

To add new external APIs (like Edison):

1. Create client in `src/llm/` or dedicated module
2. Implement retry logic with tenacity
3. Add fallback handling for degradation
4. Register timeout in `src/config.py`

---

## Appendix A: Module Dependency Graph

```
src/
├── config.py                 # No internal deps
├── tracing.py               # Depends on: config
├── utils/
│   ├── validation.py        # No internal deps
│   ├── schema_validation.py # Depends on: schemas
│   └── subprocess_env.py    # No internal deps
├── llm/
│   └── claude_client.py     # Depends on: config
├── agents/
│   ├── base.py              # Depends on: llm, best_practices
│   ├── registry.py          # Depends on: llm
│   ├── orchestrator.py      # Depends on: registry, base, feedback, cache
│   ├── workflow.py          # Depends on: agents, cache, tracing
│   └── ...                  # Individual agents depend on: base
├── evidence/
│   └── store.py             # Depends on: config, utils
├── citations/
│   └── registry.py          # Depends on: utils
├── claims/
│   └── gates.py             # Depends on: utils
└── pipeline/
    ├── runner.py            # Depends on: all workflows
    └── degradation.py       # Depends on: utils
```

---

## Appendix B: Key Design Decisions

| Decision | Rationale |
|----------|-----------|
| **Filesystem-first storage** | Inspectable outputs, simple recovery, git-friendly |
| **JSON Schema contracts** | Explicit data contracts, automated validation |
| **Append-only evidence ledger** | Full audit trail, no data loss |
| **Task-based model selection** | Cost optimization, appropriate capability matching |
| **Graceful degradation** | Pipeline resilience, partial results over failures |
| **Version-tracked cache** | Resumable workflows, revision history |
| **Permission-based inter-agent calls** | Security, controlled agent coordination |

---

*Last updated: January 2026*
