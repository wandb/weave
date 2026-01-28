# agent_eval

A framework for systematically evaluating AI coding agents against defined skills and tasks.

Inspired by the [OpenAI blog post on testing agent skills](https://developers.openai.com/blog/eval-skills/).

## Overview

`agent_eval` orchestrates running agent harnesses (OpenCode, Codex, Claude, etc.) against defined tasks in containerized sandboxes, captures execution artifacts, and feeds them to scorers for evaluation.

```
                    +-----------------+
                    |   Eval Config   |
                    |   (eval.yaml)   |
                    +--------+--------+
                             |
                             v
                    +--------+--------+
                    |    Executor     |
                    |  (orchestrates) |
                    +--------+--------+
                             |
              +--------------+--------------+
              |              |              |
              v              v              v
        +-----+-----+  +-----+-----+  +-----+-----+
        |  Task 1   |  |  Task 2   |  |  Task N   |
        | (Docker)  |  | (Docker)  |  | (Docker)  |
        +-----+-----+  +-----+-----+  +-----+-----+
              |              |              |
              v              v              v
        +-----+-----+  +-----+-----+  +-----+-----+
        |  Scorers  |  |  Scorers  |  |  Scorers  |
        +-----------+  +-----------+  +-----------+
              |              |              |
              +--------------+--------------+
                             |
                             v
                    +--------+--------+
                    |  Results/Weave  |
                    +-----------------+
```

## Quick Start

### Prerequisites

- Python 3.10+
- Docker (for running agents in containers)
- API keys for the models you want to test

### Installation

```bash
# From the weave repo root
pip install -e ".[agent_eval]"
```

### Running an Evaluation

```bash
# Check required environment variables
python -m agent_eval.cli check-env agent_eval/examples/hello-world/eval.yaml

# Run the evaluation
python -m agent_eval.cli run agent_eval/examples/hello-world/eval.yaml

# Run with parallel execution
python -m agent_eval.cli run agent_eval/examples/hello-world/eval.yaml --parallel 4

# Run with Weave logging
python -m agent_eval.cli run agent_eval/examples/hello-world/eval.yaml --weave team/project

# View results
python -m agent_eval.cli show agent_eval/examples/hello-world/results/run_<ID>
```

## Core Concepts

| Concept | Description |
|---------|-------------|
| **Skill** | A definition file (e.g., SKILL.md) that instructs an agent what it can do |
| **Harness** | An agent CLI + model combination (e.g., OpenCode + claude-sonnet) |
| **Driver** | Sandbox runtime that executes harnesses (Docker) |
| **Task** | User prompt + timeout + expected behavior |
| **Scorer** | Program that evaluates artifacts and outputs structured scores |

## Configuration

Evaluations are defined in YAML files:

```yaml
version: "1.0"
name: my-eval
description: Evaluate coding agents on file creation tasks

# Matrix of harness/model combinations to test
matrix:
  harness:
    - type: opencode
      model: gpt-4o
    - type: opencode
      model: anthropic/claude-sonnet-4-20250514

# Execution environment
driver:
  type: docker

environment:
  base_image: node:20-slim

# Skill definition (SKILL.md, AGENTS.md, etc.)
skill:
  path: ./skill

# Tasks to run
tasks:
  - id: create-file
    prompt: "Create a hello.txt file with a greeting"
    timeout: 60

# Scoring criteria
scoring:
  # Rule-based checks
  deterministic:
    checks:
      - type: file_exists
        path: hello.txt
      - type: file_contains
        path: hello.txt
        pattern: "[Hh]ello"

  # LLM-based evaluation
  rubric:
    model: gpt-4o
    prompt: |
      Evaluate the output against these criteria:
      1. **greeting**: Does it contain a proper greeting?
      2. **tone**: Is the tone friendly?

# Network access for API calls
network:
  allowed_hosts:
    - api.openai.com
    - api.anthropic.com

# Output configuration
output:
  directory: ./results
```

## Supported Harnesses

| Harness | Description | Required Env Vars |
|---------|-------------|-------------------|
| `opencode` | OpenCode CLI | `OPENAI_API_KEY` or `ANTHROPIC_API_KEY` |
| `codex` | OpenAI Codex CLI | `OPENAI_API_KEY` |
| `claude` | Anthropic Claude CLI | `ANTHROPIC_API_KEY` |
| `openai-agent` | Simple OpenAI API agent | `OPENAI_API_KEY` |

## Scorers

### Deterministic Scorer

Rule-based checks that always produce the same result:

```yaml
scoring:
  deterministic:
    checks:
      # File existence
      - type: file_exists
        path: output.txt
      
      # File content pattern (regex)
      - type: file_contains
        path: output.txt
        pattern: "expected content"
      
      # Trajectory/log search
      - type: trajectory_contains
        pattern: "command executed"
```

### LLM Rubric Scorer

Qualitative evaluation using an LLM judge:

```yaml
scoring:
  rubric:
    model: gpt-4o
    prompt: |
      Evaluate the workspace against these criteria:
      
      1. **correctness**: Does the code work?
      2. **style**: Is it well-formatted?
      3. **completeness**: Are all requirements met?
      
      Score each criterion.
```

The LLM scorer:
- Runs in its own Docker container for isolation
- Respects `.gitignore` when collecting workspace context
- Returns structured pass/fail for each criterion

## Directory Structure

```
agent_eval/
├── __init__.py
├── cli.py                 # Click CLI (run, show, validate, check-env)
├── executor.py            # Parallel job orchestration
├── artifacts.py           # Artifact directory management
├── metrics.py             # Token usage, command counts, latency
├── reporter.py            # Weave integration
├── config/
│   ├── schema.py          # Pydantic models
│   └── loader.py          # YAML parsing
├── drivers/
│   ├── base.py            # Driver protocol
│   └── docker.py          # Docker container execution
├── harnesses/
│   ├── base.py            # HarnessAdapter protocol
│   ├── registry.py        # Harness registration
│   ├── opencode.py        # OpenCode adapter
│   ├── codex.py           # Codex adapter
│   ├── claude.py          # Claude adapter
│   └── openai_agent.py    # Simple OpenAI agent
├── scorers/
│   ├── base.py            # Scorer protocol
│   ├── deterministic.py   # Rule-based checks
│   └── llm_rubric.py      # LLM evaluation
├── adapters/              # Shell/JS scripts for harnesses
│   ├── opencode-adapter.sh
│   ├── codex-adapter.sh
│   └── openai-agent-adapter.js
└── examples/
    ├── hello-world/       # Multi-model proof-of-concept
    ├── minimal/           # Simplest example
    ├── minimal-openai/    # OpenAI agent example
    └── setup-demo-app/    # Full example from OpenAI blog
```

## Artifact Output

Each run creates structured artifacts:

```
results/
└── run_20240115_143022/
    ├── metadata.json           # Run config, timestamps
    └── task-id_harness_model/
        ├── metadata.json       # Task config, metrics
        ├── trajectory.jsonl    # Agent execution trace
        ├── workspace/          # Final filesystem state
        └── scores/
            ├── deterministic.json
            └── rubric.json
```

## Weave Integration

Results can be logged to [Weave](https://wandb.ai/site/weave) for visualization and comparison:

```bash
python -m agent_eval.cli run eval.yaml --weave wandb-team/my-project
```

Data model mapping:
- **Weave Evaluation** = agent_eval config (dataset of tasks + scorers)
- **Weave Eval Run** = one harness/model running against all tasks
- **Prediction** = one task execution with its scores

## CLI Reference

```bash
# Run an evaluation
python -m agent_eval.cli run <config.yaml> [options]
  --parallel N       Run N tasks concurrently (default: 1)
  --weave PROJECT    Log results to Weave project
  --task ID          Run only specific task
  --harness TYPE     Use only specific harness type

# Show results from a previous run
python -m agent_eval.cli show <results-dir>

# Validate config without running
python -m agent_eval.cli validate <config.yaml>

# Check required environment variables
python -m agent_eval.cli check-env <config.yaml>
```

## Development

### Running Tests

```bash
# Unit tests
pytest agent_eval/tests/

# Integration test (requires Docker)
python -m agent_eval.cli run agent_eval/examples/minimal/eval.yaml
```

### Adding a New Harness

1. Create `harnesses/{name}.py` implementing `HarnessAdapter`
2. Register in `harnesses/registry.py`
3. Create adapter script in `adapters/{name}-adapter.sh`
4. Add to `HarnessType` enum in `config/schema.py`

### Adding a New Scorer

1. Create `scorers/{name}.py` implementing `Scorer`
2. Add config to `ScoringConfig` in `config/schema.py`
3. Wire up in `executor.py`

## Future Work

- **Modal driver** - Cloud execution for parallelization
- **Trajectory normalization** - Convert vendor formats to common schema
- **GitHub Action** - CI integration for running evals on PRs
- **Caching** - Skip unchanged harness/task combinations
- **Cost tracking** - Track API costs per run
