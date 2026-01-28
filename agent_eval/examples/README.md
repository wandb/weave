# agent_eval Examples

This directory contains example evaluations demonstrating how to use `agent_eval`.

## Examples

### setup-demo-app

The primary example, based on the [OpenAI blog post on testing agent skills](https://developers.openai.com/blog/eval-skills/).

Evaluates a skill that scaffolds a Vite + React + Tailwind demo app with:
- Explicit skill invocation tests
- Implicit triggering tests
- Negative control tests (skill should NOT trigger)
- Deterministic file/command checks
- LLM rubric scoring for style

```bash
agent-eval run setup-demo-app/eval.yaml
```

### minimal

The simplest possible example to get started.

```bash
agent-eval run minimal/eval.yaml
```

## Running Examples

1. Ensure required environment variables are set:
   ```bash
   agent-eval check-env setup-demo-app/eval.yaml
   ```

2. Run the evaluation:
   ```bash
   agent-eval run setup-demo-app/eval.yaml
   ```

3. Run a single task for debugging:
   ```bash
   agent-eval run setup-demo-app/eval.yaml --task explicit-invoke --harness codex:gpt-4o
   ```

4. Dry run to see what would execute:
   ```bash
   agent-eval run setup-demo-app/eval.yaml --dry-run
   ```

## Creating Your Own Evaluation

1. Create a directory for your evaluation
2. Add a `skill/SKILL.md` file with your skill definition
3. Create an `eval.yaml` config file
4. Define tasks and scoring criteria
5. Run with `agent-eval run your-eval/eval.yaml`

See the examples for config file templates.
