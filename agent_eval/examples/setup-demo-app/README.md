# Setup Demo App Evaluation

This example is based on the [OpenAI blog post on testing agent skills](https://developers.openai.com/blog/eval-skills/).

## Skill Under Test

The `setup-demo-app` skill scaffolds a Vite + React + Tailwind demo app with:
- TypeScript components
- Functional components only
- Tailwind for styling
- Minimal, consistent file structure

## Tasks

| Task ID | Description | Expected Trigger |
|---------|-------------|------------------|
| `explicit-invoke` | Explicitly references the skill by name | true |
| `implicit-invoke` | Describes what the skill does without naming it | true |
| `negative-control` | Related request that should NOT trigger the skill | false |

## Harness Matrix

This evaluation runs against multiple models via OpenCode:
- `openai/gpt-4o` - OpenAI's GPT-4o model
- `anthropic/claude-sonnet-4-20250514` - Anthropic's Claude Sonnet 4

## Scoring

### Deterministic Checks
- **File existence**: package.json, Header.tsx, Card.tsx, index.css, vite.config.ts
- **Command execution**: npm install, npm create vite
- **File content patterns**: tailwindcss import in CSS

### LLM Rubric
When enabled, evaluates qualitative aspects:
- **vite**: Vite + React + TypeScript project properly configured
- **tailwind**: Tailwind configured via @tailwindcss/vite plugin
- **structure**: src/components contains Header.tsx and Card.tsx
- **style**: Functional components styled with Tailwind classes

## Metrics Captured

Each run captures:
- **Token usage**: Input, output, and total tokens
- **Latency**: Total execution time
- **Command count**: Number of shell commands executed
- **Tool calls**: Number of tool invocations
- **File operations**: Reads and writes

## Running

```bash
# From repo root
cd agent_eval/examples/setup-demo-app

# Check environment variables are set
python -m agent_eval.cli check-env eval.yaml

# Run full evaluation (all tasks × all harnesses)
python -m agent_eval.cli run eval.yaml

# Run single task
python -m agent_eval.cli run eval.yaml --task explicit-invoke

# Run with specific harness
python -m agent_eval.cli run eval.yaml --harness opencode:gpt-4o

# Dry run to see what would execute
python -m agent_eval.cli run eval.yaml --dry-run

# View results
python -m agent_eval.cli show results/run_<ID>
```

## Environment Variables

Required:
- `OPENAI_API_KEY` - For GPT-4o model and LLM rubric scoring
- `ANTHROPIC_API_KEY` - For Claude model

## Expected Results

For a well-implemented skill:
- `explicit-invoke`: Should pass all deterministic checks
- `implicit-invoke`: Should trigger and pass all checks  
- `negative-control`: Should NOT create a new project (expected to "fail" file checks)

## Interpreting Results

After running, use `python -m agent_eval.cli show <results_path>` to see:
- Pass/fail status for each task × harness combination
- Individual check results with explanations
- Token usage and execution metrics
- Workspace files created

Compare across models to see:
- Which model follows instructions more precisely
- Token efficiency differences
- Execution time differences
