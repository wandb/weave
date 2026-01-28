# agent_eval - Implementation Plan

A lightweight framework for evaluating agent skills systematically.

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
weave/agent_eval/
├── __init__.py              # Public API exports
├── cli.py                   # Click CLI entry point
├── config/
│   ├── __init__.py
│   ├── schema.py            # Pydantic models
│   └── loader.py            # YAML parsing
├── harnesses/
│   ├── __init__.py
│   ├── base.py              # HarnessAdapter protocol
│   ├── registry.py          # Harness registration
│   ├── codex.py             # OpenAI Codex
│   ├── claude.py            # Anthropic Claude
│   ├── opencode.py          # OpenCode
│   └── generic.py           # Configurable generic
├── drivers/
│   ├── __init__.py
│   ├── base.py              # Driver protocol
│   └── docker.py            # Docker/OrbStack
├── scorers/
│   ├── __init__.py
│   ├── base.py              # Scorer protocol
│   ├── deterministic.py     # File/command checks
│   └── llm_rubric.py        # LLM-based grading
├── executor.py              # Job orchestration
├── artifacts.py             # Artifact management
└── reporter.py              # Weave integration

weave/agent_eval_adapters/   # Shell scripts for harnesses
├── codex-adapter.sh
├── claude-adapter.sh
└── opencode-adapter.sh

weave/agent_eval_examples/   # Reference examples
├── README.md
├── setup-demo-app/          # Main example from OpenAI blog
│   ├── eval.yaml
│   ├── skill/SKILL.md
│   └── scorers/
└── minimal/                 # Simplest example
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

### Milestone 1: End-to-End with Codex (MVP)

**Goal**: `agent-eval run examples/setup-demo-app/eval.yaml` produces scores

| File | Purpose |
|------|---------|
| `config/schema.py` | Pydantic models for EvalConfig, TaskConfig, HarnessConfig, etc. |
| `config/loader.py` | YAML parsing and validation |
| `drivers/base.py` | Driver protocol definition |
| `drivers/docker.py` | Docker image building, job execution, artifact collection |
| `harnesses/base.py` | HarnessAdapter protocol |
| `harnesses/codex.py` | Codex CLI adapter |
| `scorers/base.py` | Scorer protocol |
| `scorers/deterministic.py` | File exists, file contains, trajectory contains |
| `artifacts.py` | Artifact directory management |
| `executor.py` | Single-threaded job orchestration |
| `cli.py` | `run` and `validate` commands |

### Milestone 2: Full Scoring Pipeline

| File | Purpose |
|------|---------|
| `scorers/llm_rubric.py` | LLM-based grading with JSON schema output |
| `scorers/custom.py` | User-provided scorer containers |
| Score aggregation in `executor.py` | Combine multiple scorer outputs |

### Milestone 3: Multi-Harness Support

| File | Purpose |
|------|---------|
| `harnesses/claude.py` | Claude CLI adapter |
| `harnesses/opencode.py` | OpenCode CLI adapter |
| `harnesses/generic.py` | Configurable generic adapter |
| Matrix expansion in `executor.py` | Generate harness × task combinations |

### Milestone 4: Parallelization & Reporting

| File | Purpose |
|------|---------|
| Async execution in `executor.py` | Parallel container runs |
| `reporter.py` | Weave integration for logging |
| Summary generation | Aggregate metrics and reports |

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

- **Modal driver** - Cloud execution for parallelization
- **Trajectory normalization** - Convert vendor formats to common schema
- **GitHub Action** - CI integration
- **Web UI** - Results browsing and comparison
- **Caching** - Skip unchanged harness runs

## Development Notes

### Running Tests

```bash
# From repo root
nox --no-install -e "tests-3.12(shard='trace')" -- tests/agent_eval/
```

### Local Development

```bash
# Install in editable mode
pip install -e ".[agent_eval]"

# Run CLI
agent-eval --help
agent-eval run examples/setup-demo-app/eval.yaml
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
