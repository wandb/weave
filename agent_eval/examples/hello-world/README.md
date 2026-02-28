# Hello World Evaluation

The simplest possible proof-of-concept for `agent_eval`, demonstrating all primary features.

## What This Tests

| Feature | Implementation |
|---------|----------------|
| Multiple models | GPT-4o + Claude Sonnet 4 |
| Multiple tasks | `create-greeting` + `welcome-message` |
| Rule-based scoring | File exists + content pattern check |
| LLM-based scoring | Evaluates greeting quality, tone, and length |

## Matrix

This evaluation runs **2 tasks × 2 models = 4 combinations**:

| Task | GPT-4o | Claude |
|------|--------|--------|
| create-greeting | ✓ | ✓ |
| welcome-message | ✓ | ✓ |

## Scoring

### Deterministic Checks
- `file_exists`: hello.txt must be created
- `file_contains`: Must contain "Hello" (case-insensitive)

### LLM Rubric
Evaluates three criteria:
- **greeting**: Proper greeting starting with "Hello"
- **tone**: Friendly and welcoming
- **length**: Appropriate length (1-3 sentences)

## Running

```bash
# From repo root
python -m agent_eval.cli run agent_eval/examples/hello-world/eval.yaml

# Run with more parallelism
python -m agent_eval.cli run agent_eval/examples/hello-world/eval.yaml --parallel 4

# Run just one model
python -m agent_eval.cli run agent_eval/examples/hello-world/eval.yaml --harness opencode:gpt-4o

# Dry run
python -m agent_eval.cli run agent_eval/examples/hello-world/eval.yaml --dry-run

# Log results to Weave for visualization and comparison
python -m agent_eval.cli run agent_eval/examples/hello-world/eval.yaml --weave your-team/agent-eval
```

## Weave Integration

Results can be logged to [Weave](https://docs.wandb.ai/weave) for visualization and model comparison.

### Using CLI flag
```bash
python -m agent_eval.cli run eval.yaml --weave your-team/project-name
```

### Using config file
```yaml
output:
  directory: ./results
  weave:
    project: your-team/project-name
```

### What gets logged to Weave
- **One eval per config**: The evaluation name becomes the Weave dataset
- **One eval run per model**: Each harness/model combo gets its own eval run
- **Tasks as predictions**: Each task becomes a row in the eval
- **Scores as metrics**: Both deterministic and rubric scores are logged
- **Metrics**: Token usage, latency, command counts

## Expected Output

All 4 combinations should pass both deterministic and rubric checks, producing hello.txt files like:

```
Hello! Welcome to the world of coding. Have a great day!
```

## Environment Variables Required

- `OPENAI_API_KEY` - For GPT-4o model and LLM rubric
- `ANTHROPIC_API_KEY` - For Claude model
