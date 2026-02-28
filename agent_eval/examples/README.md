# agent_eval Examples

This directory contains example evaluations demonstrating how to use `agent_eval`.

## Examples

### hello-world (Recommended Starting Point)

A minimal proof-of-concept demonstrating:
- Multiple models (GPT-4o and Claude Sonnet)
- Multiple tasks (2 file creation tasks)
- Rule-based scoring (deterministic file checks)
- LLM-based scoring (qualitative rubric evaluation)

```bash
python -m agent_eval.cli run agent_eval/examples/hello-world/eval.yaml
```

### setup-demo-app

The full example based on the [OpenAI blog post on testing agent skills](https://developers.openai.com/blog/eval-skills/).

Evaluates a skill that scaffolds a Vite + React + Tailwind demo app with:
- Multiple models (GPT-4o, GPT-4.1, Claude Sonnet, Claude Opus)
- Explicit skill invocation tests
- Implicit triggering tests
- Negative control tests (skill should NOT trigger)
- Deterministic file/command checks
- LLM rubric scoring for code quality

```bash
python -m agent_eval.cli run agent_eval/examples/setup-demo-app/eval.yaml
```

## Running Examples

1. **Check required environment variables:**
   ```bash
   python -m agent_eval.cli check-env agent_eval/examples/hello-world/eval.yaml
   ```

2. **Run the evaluation:**
   ```bash
   python -m agent_eval.cli run agent_eval/examples/hello-world/eval.yaml
   ```

3. **Run with parallel execution:**
   ```bash
   python -m agent_eval.cli run agent_eval/examples/hello-world/eval.yaml --parallel 4
   ```

4. **Run with Weave logging:**
   ```bash
   python -m agent_eval.cli run agent_eval/examples/hello-world/eval.yaml --weave team/project
   ```

5. **View results from a previous run:**
   ```bash
   python -m agent_eval.cli show agent_eval/examples/hello-world/results/run_<ID>
   ```

## Creating Your Own Evaluation

1. Create a directory for your evaluation
2. Add a `skill/SKILL.md` file with your skill definition
3. Create an `eval.yaml` config file
4. Define tasks and scoring criteria
5. Run with `python -m agent_eval.cli run your-eval/eval.yaml`

### Example Config Structure

```yaml
version: "1.0"
name: my-eval

matrix:
  harness:
    - type: opencode
      model: gpt-4o

driver:
  type: docker

environment:
  base_image: node:20-slim

skill:
  path: ./skill

tasks:
  - id: my-task
    prompt: "Do the thing"
    timeout: 60

scoring:
  deterministic:
    checks:
      - type: file_exists
        path: output.txt

network:
  allowed_hosts:
    - api.openai.com

output:
  directory: ./results
```

See the individual example directories for complete config file templates.
