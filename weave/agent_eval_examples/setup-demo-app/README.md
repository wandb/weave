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
| `contextual-invoke` | Adds domain context while needing the skill | true |
| `negative-control` | Related request that should NOT trigger the skill | false |

## Scoring

### Deterministic Checks
- File existence (package.json, Header.tsx, Card.tsx, etc.)
- Command execution (npm install, npm create vite)
- File content patterns (tailwindcss import)

### LLM Rubric (optional)
When enabled, evaluates:
- Vite + React + TypeScript configuration
- Tailwind setup via @tailwindcss/vite
- Component structure
- Styling conventions

## Running

```bash
# Check environment variables
agent-eval check-env eval.yaml

# Run full evaluation
agent-eval run eval.yaml

# Run single task
agent-eval run eval.yaml --task explicit-invoke

# Dry run
agent-eval run eval.yaml --dry-run
```

## Expected Results

For a well-implemented skill:
- `explicit-invoke`: Should pass all checks
- `implicit-invoke`: Should trigger and pass all checks
- `contextual-invoke`: Should trigger and pass all checks
- `negative-control`: Should NOT create a new project (expected to "fail" checks, which is correct)
