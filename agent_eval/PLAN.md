# agent_eval - Implementation Plan

A lightweight framework for evaluating agent skills systematically.

## Implementation Status

| Milestone | Status | Notes |
|-----------|--------|-------|
| M1: End-to-End with Codex (MVP) | COMPLETE | Core framework working |
| M2: Full Scoring Pipeline | COMPLETE | Deterministic + LLM rubric scorers |
| M3: Multi-Harness Support | COMPLETE | OpenCode, Codex, Claude, OpenAI Agent |
| M4: Parallelization & Reporting | COMPLETE | Async execution + Weave integration |

## Overview

`agent_eval` orchestrates running agent harnesses (Codex, Claude, OpenCode, etc.) against 
defined tasks in containerized sandboxes, captures execution artifacts, and feeds them to 
scorers for evaluation.

**Design Reference**: https://developers.openai.com/blog/eval-skills/

## Core Concepts

| Concept | Description |
|---------|-------------|
| **Skill** | A definition file (e.g., SKILL.md) that instructs an agent |
| **Harness** | An agent CLI + model combination (e.g., Codex + gpt-4o) |
| **Driver** | Sandbox runtime that executes harnesses (Docker, Modal) |
| **Task** | User instruction + environment snapshot + scoring spec |
| **Scorer** | Program that evaluates artifacts and outputs structured scores |

## Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           ORCHESTRATOR (Python)                              │
│  • Parse eval config (YAML)                                                  │
│  • Expand matrix configurations                                              │
│  • Schedule jobs to driver                                                   │
│  • Collect results → Weave                                                   │
└───────────────────────────────────────┬──────────────────────────────────────┘
                                        │
                    ┌───────────────────┴───────────────────┐
                    │           DRIVER INTERFACE            │
                    │  • build_image(base, layers, skill)   │
                    │  • run_job(image, command, mounts)    │
                    │  • collect_artifacts(job) → dir       │
                    └───────────────────┬───────────────────┘
                                        │
                    ┌───────────────────┴───────────────────┐
                    │                                       │
              ┌─────▼─────┐                         ┌───────▼───────┐
              │  DOCKER   │                         │    MODAL      │
              │  DRIVER   │                         │   (future)    │
              └───────────┘                         └───────────────┘
```

## Directory Structure

```
agent_eval/                    # Standalone module (sibling to weave/)
├── __init__.py                # Public API exports
├── cli.py                     # Click CLI entry point (run, show, validate, check-env)
├── executor.py                # Async job orchestration with parallel execution
├── artifacts.py               # Artifact directory management
├── metrics.py                 # Token usage, command counts, latency extraction
├── reporter.py                # Weave EvaluationLogger integration
├── config/
│   ├── __init__.py
│   ├── schema.py              # Pydantic models for eval config
│   └── loader.py              # YAML parsing and validation
├── harnesses/
│   ├── __init__.py
│   ├── base.py                # HarnessAdapter protocol
│   ├── registry.py            # Harness type -> adapter mapping
│   ├── codex.py               # OpenAI Codex CLI adapter
│   ├── claude.py              # Anthropic Claude CLI adapter
│   ├── opencode.py            # OpenCode CLI adapter (default)
│   ├── openai_agent.py        # Simple OpenAI API agent
│   └── generic.py             # Configurable generic adapter
├── drivers/
│   ├── __init__.py
│   ├── base.py                # Driver protocol (build_image, run_job, cleanup)
│   └── docker.py              # Docker container execution
├── scorers/
│   ├── __init__.py
│   ├── base.py                # Scorer protocol
│   ├── deterministic.py       # File exists, file contains, trajectory contains
│   └── llm_rubric.py          # LLM-based grading (runs in Docker container)
├── adapters/                  # Shell/JS scripts injected into containers
│   ├── codex-adapter.sh
│   ├── claude-adapter.sh
│   ├── opencode-adapter.sh
│   └── openai-agent-adapter.js
├── tests/                     # Unit tests
│   ├── test_config.py
│   ├── test_harnesses.py
│   ├── test_artifacts.py
│   └── test_scorers.py
└── examples/                  # Reference examples
    ├── README.md
    ├── hello-world/           # Multi-model proof-of-concept (2 tasks x 2 models)
    └── setup-demo-app/        # Full example from OpenAI blog (4 models)
```

## Execution Flow

```
1. LOAD CONFIG
   • Parse YAML → EvalConfig
   • Expand matrix → list of (harness, task) combinations
   • Resolve required env keys → fail fast if missing

2. BUILD IMAGES
   • Build harness image (base + env layers + skill + adapter)
   • Build scorer images (if custom)

3. RUN HARNESS JOBS (parallelizable)
   For each (harness, task) combination:
   • driver.run_job(harness_image, cmd, env, timeout)
   • Collect artifacts → artifacts/{run_id}/{task_id}/

4. RUN SCORER JOBS (parallelizable per task)
   For each task's artifacts:
   • Run deterministic scorer
   • Run LLM rubric scorer
   • Run custom scorers
   • Aggregate scores → artifacts/{run_id}/{task_id}/scores/

5. REPORT
   • Aggregate all scores
   • Log to Weave (optional)
   • Generate summary report
```

## Implementation Milestones

### Milestone 1: End-to-End with Codex (MVP) - COMPLETE

**Goal**: `agent-eval run examples/setup-demo-app/eval.yaml` produces scores

| File | Purpose | Status |
|------|---------|--------|
| `config/schema.py` | Pydantic models for EvalConfig, TaskConfig, HarnessConfig, etc. | Done |
| `config/loader.py` | YAML parsing and validation | Done |
| `drivers/base.py` | Driver protocol definition | Done |
| `drivers/docker.py` | Docker image building, job execution, artifact collection | Done |
| `harnesses/base.py` | HarnessAdapter protocol | Done |
| `harnesses/codex.py` | Codex CLI adapter | Done |
| `scorers/base.py` | Scorer protocol | Done |
| `scorers/deterministic.py` | File exists, file contains, trajectory contains | Done |
| `artifacts.py` | Artifact directory management | Done |
| `executor.py` | Single-threaded job orchestration | Done |
| `cli.py` | `run` and `validate` commands | Done |

### Milestone 2: Full Scoring Pipeline - COMPLETE

| File | Purpose | Status |
|------|---------|--------|
| `scorers/llm_rubric.py` | LLM-based grading with JSON schema output | Done |
| `scorers/custom.py` | User-provided scorer containers | Deferred |
| Score aggregation in `executor.py` | Combine multiple scorer outputs | Done |

**Notes**: LLM rubric scorer runs in its own Docker container for isolation, respects .gitignore when collecting workspace context.

### Milestone 3: Multi-Harness Support - COMPLETE

| File | Purpose | Status |
|------|---------|--------|
| `harnesses/claude.py` | Claude CLI adapter | Done |
| `harnesses/opencode.py` | OpenCode CLI adapter | Done |
| `harnesses/openai_agent.py` | Simple OpenAI API agent | Done |
| `harnesses/generic.py` | Configurable generic adapter | Done |
| Matrix expansion in `executor.py` | Generate harness x task combinations | Done |

### Milestone 4: Parallelization & Reporting - COMPLETE

| File | Purpose | Status |
|------|---------|--------|
| Async execution in `executor.py` | Parallel container runs with semaphore | Done |
| `reporter.py` | Weave EvaluationLogger integration | Done |
| `metrics.py` | Token usage, latency, command counts | Done |
| Summary generation | Aggregate metrics and reports | Done |

**Notes**: 
- Parallel execution uses asyncio with configurable concurrency (`--parallel N`)
- Weave integration logs each check as its own score for cleaner visualization
- Metrics extracted from harness logs (supports OpenCode, Codex formats)

## Key Contracts

### Harness Adapter Contract

Environment variables passed to harness container:

```
AGENT_EVAL_PROMPT       - The user prompt
AGENT_EVAL_SKILL_PATH   - Path to skill directory  
AGENT_EVAL_WORKDIR      - Working directory
AGENT_EVAL_TIMEOUT      - Timeout in seconds
```

Required outputs:

```
/artifacts/trajectory.jsonl   - Execution trace (vendor format OK)
/artifacts/workspace/         - Final filesystem state
/artifacts/metadata.json      - Job metadata
```

### Scorer Contract

Inputs (mounted read-only):

```
/artifacts/           - Harness outputs
/config/scorer.yaml   - Scorer configuration (if needed)
```

Required output:

```json
// /output/score.json
{
  "overall_pass": true,
  "score": 85,
  "checks": [
    {"id": "check_id", "pass": true, "notes": "..."}
  ],
  "metadata": {"scorer": "...", "version": "...", "duration_ms": 123}
}
```

### Artifact Directory Structure

```
artifacts/
└── {run_id}/
    └── {task_id}/
        ├── metadata.json           # Task config, timestamps, harness info
        ├── trajectory.jsonl        # Full agent execution trace
        ├── workspace/              # Final filesystem state
        └── scores/
            ├── deterministic.json
            ├── rubric.json
            └── custom.json
```

## Configuration Reference

### Minimal Example

```yaml
version: "1.0"
name: my-eval

driver:
  type: docker

environment:
  base_image: python:3.12-slim

skill:
  path: ./skill

tasks:
  - id: basic
    prompt: "Do the thing"

scoring:
  deterministic:
    checks:
      - type: file_exists
        path: output.txt
```

### Full Example

See `agent_eval_examples/setup-demo-app/eval.yaml` for a complete example
with matrix expansion, multiple scorers, and LLM rubric grading.

## API Key Resolution

Harnesses declare their required environment variables. Before execution:

1. Collect all required keys from harness, environment, and scorers
2. Resolve from host environment
3. Fail fast with clear error if any keys are missing
4. Pass resolved keys to container via environment

```python
def resolve_required_env(harness, environment, scorers) -> dict[str, str]:
    required = set()
    required.update(harness.required_env_keys())
    required.update(environment.additional_env_keys)
    for scorer in scorers:
        required.update(scorer.required_env_keys())
    
    env = {}
    missing = []
    for key in required:
        if value := os.environ.get(key):
            env[key] = value
        else:
            missing.append(key)
    
    if missing:
        raise EnvironmentError(f"Missing: {missing}")
    return env
```

## Network Configuration

Scorer containers get restricted network access via allowlist:

```yaml
network:
  allowed_hosts:
    - api.openai.com
    - api.anthropic.com
```

Implementation via Docker network policies or iptables rules.

## Future Work

| Feature | Priority | Notes |
|---------|----------|-------|
| **Modal driver** | High | Cloud execution for better parallelization |
| **Caching** | High | Skip unchanged harness/task combinations |
| **Cost tracking** | Medium | Track API costs per run |
| **Trajectory normalization** | Medium | Convert vendor formats to common schema |
| **GitHub Action** | Medium | CI integration for running evals on PRs |
| **Custom scorers** | Low | User-provided scorer containers |
| **Web UI** | Low | Results browsing and comparison |

## Known Issues

- Docker must be running for any evaluation to work
- LLM rubric scorer requires network access to OpenAI API
- Token metrics extraction only works for OpenCode and Codex harnesses currently

## Development Notes

### Running Tests

```bash
# Unit tests
pytest agent_eval/tests/

# Integration test (requires Docker)
python -m agent_eval.cli run agent_eval/examples/minimal/eval.yaml
```

### Local Development

```bash
# Run CLI directly
python -m agent_eval.cli --help
python -m agent_eval.cli run agent_eval/examples/hello-world/eval.yaml

# With parallel execution
python -m agent_eval.cli run agent_eval/examples/hello-world/eval.yaml --parallel 4

# With Weave logging
python -m agent_eval.cli run agent_eval/examples/hello-world/eval.yaml --weave team/project

# Check environment variables
python -m agent_eval.cli check-env agent_eval/examples/hello-world/eval.yaml

# View results
python -m agent_eval.cli show agent_eval/examples/hello-world/results/run_<ID>
```

### Adding a New Harness

1. Create `harnesses/{name}.py` implementing `HarnessAdapter`
2. Register in `harnesses/registry.py`
3. Create adapter script in `agent_eval_adapters/{name}-adapter.sh`
4. Add tests in `tests/agent_eval/harnesses/test_{name}.py`

### Adding a New Scorer

1. Create `scorers/{name}.py` implementing `Scorer`
2. Add to scoring config schema in `config/schema.py`
3. Wire up in `executor.py`
4. Add tests in `tests/agent_eval/scorers/test_{name}.py`
