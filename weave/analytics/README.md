```
        _
       /_/_      .'''.
    =O(_)))) ...'     `.
       \_\              `.    .'''
                          `..'

██╗    ██╗███████╗ █████╗ ██╗   ██╗███████╗
██║    ██║██╔════╝██╔══██╗██║   ██║██╔════╝
██║ █╗ ██║█████╗  ███████║██║   ██║█████╗
██║███╗██║██╔══╝  ██╔══██║╚██╗ ██╔╝██╔══╝
╚███╔███╔╝███████╗██║  ██║ ╚████╔╝ ███████╗
 ╚══╝╚══╝ ╚══════╝╚═╝  ╚═╝  ╚═══╝  ╚══════╝
            a n a l y t i c s
```

# Weave Analytics CLI

A command-line tool for analyzing Weave traces using LLM-powered clustering and summarization. Part of the Weave Python client.

## Overview

Weave Analytics provides AI-powered analysis of your Weave traces to help you:

- **Identify patterns** in trace behavior, failures, and outcomes
- **Cluster traces** into meaningful categories automatically
- **Summarize individual traces** with key metrics and insights
- **Debug AI systems** by understanding common failure modes

The CLI uses large language models (via LiteLLM) to analyze trace inputs, outputs, and execution trees, then groups them into coherent categories with explanations.

## Installation

Install with the analytics extras:

```bash
pip install weave[analytics]
```

Or if using uv:

```bash
uv pip install weave[analytics]
```

## Quick Start

1. **Setup credentials:**

```bash
weave analytics setup
```

This configures your W&B API key and LLM provider (Google, OpenAI, or Anthropic).

2. **Cluster traces from a Weave URL:**

```bash
weave analytics cluster "https://wandb.ai/your-team/your-project/weave/traces?filter=..." --pretty
```

3. **Summarize a single trace:**

```bash
weave analytics summarize "https://wandb.ai/your-team/your-project/weave/calls/abc123" --pretty
```

## Commands

### `weave analytics setup`

Interactive configuration wizard for setting up API keys and preferences.

**What it configures:**

- W&B API key (for fetching traces)
- LLM model and API key (for AI analysis)
- Debug entity/project (optional, for tracing the analytics pipeline itself)

**Configuration storage:** `~/.weave/analytics_config`

**Options:**

| Option | Description |
|--------|-------------|
| `--wandb-api-key` | W&B API key |
| `--llm-model` | LiteLLM model name (default: `gemini/gemini-2.5-pro`) |
| `--llm-api-key` | API key for the LLM provider |
| `--llm-provider` | Provider: `google`, `openai`, `anthropic`, or `auto` |
| `--debug-entity` | W&B entity for debug tracing |
| `--debug-project` | W&B project for debug tracing |

---

### `weave analytics cluster`

Analyze and cluster traces into pattern categories using AI.

**Input:** A Weave URL containing traces to analyze. Supports:

- Trace list URLs with filters: `https://wandb.ai/entity/project/weave/traces?filter=...`
- Individual call URLs: `https://wandb.ai/entity/project/weave/calls/abc123`

**Output:** JSON with discovered clusters, each containing:

- Category name and definition
- Count and percentage of traces
- List of trace IDs with categorization reasons

**How it works:**

1. **Fetch traces** from the Weave API based on the URL filters
2. **Draft categorization** - Each trace is analyzed individually to propose candidate categories
3. **Aggregate and cluster** - Candidate categories are merged into coherent pattern groups
4. **Final classification** - Each trace is assigned to a final category with reasoning

**Options:**

| Option | Description |
|--------|-------------|
| `--model` | LiteLLM model name |
| `--limit` | Maximum traces to analyze |
| `--max-concurrent` | Concurrent LLM calls (default: 10) |
| `--pretty` | Pretty print with Rich formatting |
| `-o, --output` | Output file path |
| `--debug` | Enable Weave tracing of the pipeline |
| `--depth` | Enable deep trace analysis with specified depth (0=disabled) |
| `--context` | User context about the AI system |

**Example output:**

```json
{
  "total_traces": 50,
  "entity": "my-team",
  "project": "my-project",
  "clusters": [
    {
      "category_name": "timeout_errors",
      "category_definition": "Traces that failed due to API timeout...",
      "count": 12,
      "percentage": 24.0,
      "traces": [...]
    }
  ]
}
```

---

### `weave analytics summarize`

Generate an LLM-powered summary of a single trace including its execution tree.

**Input:** A Weave call URL: `https://wandb.ai/entity/project/weave/calls/abc123`

**Output:** Markdown summary with:

- Trace metadata (operation, duration, status)
- Token usage and cost (if available)
- Execution flow analysis
- Key observations and potential issues

**Options:**

| Option | Description |
|--------|-------------|
| `--model` | LiteLLM model name |
| `--depth` | Max depth for execution tree (default: 5) |
| `--pretty` | Pretty print with Rich formatting |
| `-o, --output` | Output file path |

---

## Deep Trace Analysis

For complex agentic workflows, use the `--depth` option with the cluster command:

```bash
weave analytics cluster "..." --depth 5 --pretty
```

This fetches the full execution tree for each trace (nested function calls, tool invocations, etc.) and includes it in the analysis. The depth parameter controls how many levels of nested calls to include. The execution tree is automatically compacted if it exceeds token limits.

Deep analysis is useful for:

- Multi-step agent workflows
- Traces with nested LLM calls
- Understanding failure cascades

---

## Debug Mode

To trace the analytics pipeline itself (useful for debugging or understanding how clustering works):

```bash
weave analytics cluster "..." --debug
```

This logs all LLM calls to your configured debug Weave project, allowing you to inspect the prompts and responses used for categorization.

---

## Architecture

```
weave/analytics/
    main.py           - CLI entry point and command registration
    commands/
        setup.py      - Configuration wizard
        cluster.py    - Clustering command
        summarize.py  - Summarization command
    clustering.py     - Core clustering pipeline and trace utilities
    models.py         - Pydantic models for structured outputs
    prompts.py        - LLM prompts for categorization
    url_parser.py     - Weave URL parsing utilities
    weave_client.py   - Weave API client wrapper
    header.py         - CLI branding
    spinner.py        - Loading spinner utility
```

---

## Supported LLM Providers

Via LiteLLM, the following providers are supported:

| Provider | Model format | Environment variable |
|----------|-------------|---------------------|
| Google | `gemini/gemini-2.5-pro` | `GOOGLE_API_KEY` |
| OpenAI | `openai/gpt-4o` | `OPENAI_API_KEY` |
| Anthropic | `anthropic/claude-3-5-sonnet` | `ANTHROPIC_API_KEY` |

See [LiteLLM documentation](https://docs.litellm.ai/docs/providers) for additional providers.

---

## Tips

- **Start with `--pretty`** for interactive use to see progress and formatted output
- **Use `--limit`** when exploring large trace sets to reduce cost and time
- **Provide `--context`** to help the LLM understand your specific use case
- **Use `--depth N`** for agentic workflows where nested execution matters
- **Pipe to jq** for JSON processing: `weave analytics cluster "..." | jq '.clusters[0]'`

