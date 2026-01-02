# CLAUDE.md - AI Assistant Guidelines for GIA Agentic Research Pipeline

This document provides comprehensive guidance for AI assistants working with this codebase.

## Project Overview

**GIA Agentic Research Pipeline** is a fully autonomous academic research system that orchestrates multi-agent workflows from project intake to auditable research output. The north star is "no claim without traceable support".

**Author**: Gia Tenica* (me@giatenica.com)
*Gia Tenica is an anagram for Agentic AI. Gia is a fully autonomous AI researcher. See: https://giatenica.com

### Core Philosophy

- Filesystem-first: Durable artifacts (Markdown, JSON) written to project folders
- Schema-driven: JSON schemas are treated as contracts
- Gate-based: Evidence, citations, and analysis gates block or downgrade when inputs are incomplete
- Graceful degradation: When optional components fail, pipeline continues with scaffold outputs

---

## Repository Structure

```
gia-agentic-short/
├── src/                    # Source code
│   ├── agents/             # Agent implementations (A01-A25)
│   │   ├── base.py         # BaseAgent class with Claude API integration
│   │   ├── registry.py     # Agent registry with capabilities, permissions
│   │   ├── workflow.py     # Phase 1 workflow orchestrator
│   │   ├── literature_workflow.py  # Phase 2 literature workflow
│   │   ├── gap_resolution_workflow.py  # Phase 3 gap resolution
│   │   ├── orchestrator.py # AgentOrchestrator for multi-agent coordination
│   │   └── prompts/        # Prompt templates
│   ├── analysis/           # Analysis runner and gates
│   ├── citations/          # Citation registry, verification, bibliography
│   ├── claims/             # Claim generation and evidence gates
│   ├── evidence/           # Evidence pipeline (parsing, extraction, storage)
│   ├── evaluation/         # Evaluation suite runner
│   ├── literature/         # Literature gates
│   ├── llm/                # Claude API client with multi-model support
│   ├── paper/              # Paper assembly and LaTeX generation
│   ├── pipeline/           # Unified pipeline runner and context
│   ├── schemas/            # JSON schemas for validation
│   ├── utils/              # Utilities (validation, filesystem, subprocess)
│   ├── config.py           # Centralized configuration
│   └── tracing.py          # OpenTelemetry tracing
├── scripts/                # CLI entrypoints and runners
├── tests/                  # pytest test suite (497+ unit tests)
├── docs/                   # Documentation (style guide, troubleshooting)
├── evaluation/             # Evaluation inputs (test_queries.json)
├── public/                 # Public assets
└── user-input/             # User research data (gitignored)
```

---

## Agent System

### Agent Registry (A01-A25)

All agents are registered in `src/agents/registry.py`. Current registry:

| Phase | IDs | Purpose |
|-------|-----|---------|
| **Intake & Analysis** | A01-A04 | DataAnalyst, ResearchExplorer, GapAnalyst, OverviewGenerator |
| **Literature & Planning** | A05-A09 | HypothesisDeveloper, LiteratureSearcher, LiteratureSynthesizer, PaperStructurer, ProjectPlanner |
| **Gap Resolution** | A10-A11 | GapResolver, OverviewUpdater |
| **Quality & Tracking** | A12-A15 | CriticalReviewer, StyleEnforcer, ConsistencyChecker, ReadinessAssessor |
| **Evidence & Writing** | A16-A25 | EvidenceExtractor, SectionWriter, RelatedWorkWriter, RefereeReview, ResultsWriter, IntroductionWriter, MethodsWriter, DiscussionWriter, DataAnalysisExecution, DataFeasibilityValidation |

### Creating New Agents

All new agents MUST:

1. Import from `src.agents.best_practices`
2. Inherit from `BaseAgent` or use `build_enhanced_system_prompt()`
3. Register in `src/agents/registry.py` with `AgentSpec`
4. Use async/await patterns
5. Return `AgentResult` with structured metadata

```python
from src.agents.base import BaseAgent, AgentResult
from src.llm.claude_client import TaskType

class MyNewAgent(BaseAgent):
    def __init__(self, client=None):
        super().__init__(
            name="MyNewAgent",
            task_type=TaskType.DATA_ANALYSIS,
            system_prompt="Your agent's system prompt...",
            client=client,
            cache_ttl="ephemeral",
        )

    async def execute(self, context: dict) -> AgentResult:
        # Implementation
        pass
```

### Model Selection

| Task Type | Model | Use Case |
|-----------|-------|----------|
| Complex Reasoning | `claude-opus-4-5-20251101` | Research, scientific analysis, academic writing |
| Coding/Agents | `claude-sonnet-4-5-20250929` | Default for most tasks, agents, data analysis |
| High-Volume | `claude-haiku-4-5-20251001` | Classification, summarization, extraction |

---

## Development Workflow

### Prerequisites

- Python 3.11+ (tested with 3.11, 3.12, 3.13)
- `ANTHROPIC_API_KEY` environment variable (for integration tests and live runs)

### Setup

```bash
# Create virtual environment
python -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Run unit tests (no API keys required)
.venv/bin/python -m pytest tests/ -v -m unit

# Run all tests (requires ANTHROPIC_API_KEY)
.venv/bin/python -m pytest tests/ -v
```

### Running the Pipeline

Common entrypoints in `scripts/`:

| Script | Purpose |
|--------|---------|
| `run_workflow.py <folder>` | Phase 1: intake, analysis, overview |
| `run_literature_workflow.py <folder>` | Phase 2: literature search and synthesis |
| `run_gap_resolution.py <folder>` | Phase 3: gap resolution |
| `run_full_pipeline.py <folder>` | Run all phases sequentially |
| `run_writing_review_stage.py <folder>` | Writing and referee review |
| `run_paper_assembly.py <folder>` | Assemble LaTeX paper |
| `run_paper_compile.py <folder>` | Compile LaTeX to PDF |
| `run_evaluation_suite.py` | Run evaluation suite |

---

## Testing Guidelines

### Test Categories

- `@pytest.mark.unit` - Fast tests, no external dependencies (497+ tests)
- `@pytest.mark.integration` - Tests requiring API keys
- `@pytest.mark.slow` - Long-running tests

### Test Structure

```python
@pytest.mark.unit
@patch.dict('os.environ', {'ANTHROPIC_API_KEY': 'test-key'}, clear=True)
@patch('src.llm.claude_client.anthropic.Anthropic')
@patch('src.llm.claude_client.anthropic.AsyncAnthropic')
def test_feature(self, mock_async_anthropic, mock_anthropic):
    # Test implementation
```

### Commands

```bash
# Run unit tests only
.venv/bin/python -m pytest tests/ -v -m unit

# Run specific test file
.venv/bin/python -m pytest tests/test_workflow.py -v

# Run with coverage
.venv/bin/python -m pytest tests/ -v --cov=src --cov-report=term-missing
```

---

## Critical Rules

### Writing Style (NEVER violate)

1. **NEVER make up data, statistics, numbers, or facts**
2. **NEVER use emojis**
3. **NEVER use em dashes** (use semicolons, colons, or periods)
4. **ALWAYS cite sources** for quantitative claims
5. **ALWAYS include current date** in system prompts

### Banned Words (NEVER use in generated content)

```
delve, realm, harness, unlock, tapestry, paradigm, cutting-edge, revolutionize,
landscape, potential, findings, intricate, showcasing, crucial, pivotal, surpass,
meticulously, vibrant, unparalleled, underscore, leverage, synergy, innovative,
game-changer, testament, commendable, meticulous, highlight, emphasize, boast,
groundbreaking, align, foster, showcase, enhance, holistic, garner, accentuate,
pioneering, trailblazing, unleash, versatile, transformative, redefine, seamless,
optimize, scalable, robust (non-statistical), breakthrough, empower, streamline,
intelligent, smart, next-gen, frictionless, elevate, adaptive, effortless,
data-driven, insightful, proactive, mission-critical, visionary, disruptive,
reimagine, agile, customizable, personalized, unprecedented, intuitive,
leading-edge, synergize, democratize, automate, accelerate, state-of-the-art,
dynamic (non-technical), reliable, efficient, cloud-native, immersive, predictive,
transparent, proprietary, integrated, plug-and-play, turnkey, future-proof,
open-ended, AI-powered, next-generation, always-on, hyper-personalized,
results-driven, machine-first, paradigm-shifting, novel, unique, utilize, impactful
```

**Use instead**: "examine" not "delve", "use" not "utilize", "new" not "novel", "important" not "crucial"

---

## Code Conventions

### Environment and Configuration

- **Do not auto-load `.env`** at import time inside `src/` modules
- CLI entrypoints in `scripts/` may call `load_env_file_lenient()`
- Use centralized config from `src/config.py`:
  ```python
  from src.config import TIMEOUTS, FILENAMES, INTAKE_SERVER, TRACING
  ```
- Do not hardcode timeout values; use centralized config constants

### Subprocess Safety

- LLM-generated code runs with minimal environment via `build_minimal_subprocess_env()`
- Use `encoding="utf-8"` and `errors="replace"` for subprocess text handling
- Use `src.utils.subprocess_text.to_text()` for timeout exception handling

### Filesystem Safety

- Avoid unbounded `Path.rglob("*")`; cap enumerations using `INTAKE_SERVER.MAX_ZIP_FILES`
- Use `src.utils.zip_safety.extract_zip_bytes_safely()` for ZIP extraction
- Prefer project-relative path filtering when excluding directories

### Module Organization

- Do not mutate `sys.path` inside `src/` modules
- If a script needs repo-root imports, do it in `scripts/` or run via `python -m`
- Validate workflow inputs using `src.utils.validation.validate_project_folder()`

---

## Key Configuration Values

Centralized in `src/config.py`:

| Config | Environment Variable | Default |
|--------|---------------------|---------|
| Intake port | `GIA_INTAKE_PORT` | 8080 |
| Max upload size | `GIA_MAX_UPLOAD_MB` | 2048 |
| Max ZIP files | `GIA_MAX_ZIP_FILES` | 20000 |
| PDF download timeout | `GIA_PDF_DOWNLOAD_TIMEOUT` | 120s |
| LLM API timeout | N/A | 600s |
| Code execution timeout | N/A | 120s |
| Gap max iterations | `GIA_GAP_MAX_ITERATIONS` | 3 |
| Tracing enabled | `ENABLE_TRACING` | false |

---

## JSON Schemas

Located in `src/schemas/`. Schemas are contracts:

- `evidence_item.schema.json` - Evidence extracted from sources
- `citation_record.schema.json` - Citation registry entries
- `claim_record.schema.json` - Claims with evidence links
- `metric_record.schema.json` - Computed metrics
- `degradation_event.schema.json` - Graceful degradation events
- `agent_message.schema.json` - Inter-agent communication

Validate using `jsonschema` library. All schema-validated outputs must pass before proceeding.

---

## Gates and Checks

The pipeline uses gates to enforce quality:

- **Citations gate** (`src/citations/gates.py`): Verifies citation presence and formatting
- **Literature gate** (`src/literature/gates.py`): Checks literature coverage
- **Evidence gate** (`src/evidence/`): Validates evidence extraction
- **Claim gate** (`src/claims/gates.py`): Checks claims against evidence and metrics
- **Analysis gate** (`src/analysis/gates.py`): Validates computed metrics

Gates can: PASS, DOWNGRADE (continue with warnings), or BLOCK (halt pipeline).

---

## Git Practices

- **Git config**: user.name=giatenica, user.email=me@giatenica.com
- Keep research project data in `user-input/` (gitignored)
- Keep secrets out of git; `.env` is ignored
- When modifying tracked files: run unit tests, then commit and push

---

## CI/CD

GitHub Actions workflows in `.github/workflows/`:

- **ci.yml**: Tests on Python 3.11, 3.12, 3.13; linting with ruff, black, isort, mypy
- **security.yml**: Dependency review, pip-audit, safety checks

---

## Common Development Tasks

### Adding a New Agent

1. Create agent file in `src/agents/`
2. Inherit from `BaseAgent`, implement `async execute()`
3. Add `AgentSpec` to `AGENT_REGISTRY` in `src/agents/registry.py`
4. Create tests in `tests/test_<agent_name>.py`
5. Run unit tests before committing

### Modifying Schemas

1. Update schema in `src/schemas/`
2. Update any code that validates against the schema
3. Update any code that produces schema-compliant output
4. Add tests for new schema fields

### Running a Research Project

1. Create project folder with `project.json`
2. Run intake: `python scripts/run_workflow.py <folder>`
3. Run literature: `python scripts/run_literature_workflow.py <folder>`
4. Run gap resolution: `python scripts/run_gap_resolution.py <folder>`
5. Run writing: `python scripts/run_writing_review_stage.py <folder>`
6. Compile paper: `python scripts/run_paper_compile.py <folder>`

---

## Troubleshooting

- See `docs/troubleshooting.md` for common issues
- Check `workflow_*.log` files for detailed execution logs
- Enable tracing with `ENABLE_TRACING=true` for OpenTelemetry spans
- For API issues, verify `ANTHROPIC_API_KEY` is set correctly

---

*Last updated: January 2026*
