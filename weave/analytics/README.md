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
- **Annotate traces** with failure analysis categories visible in Weave UI
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
weave analytics cluster "https://wandb.ai/your-team/your-project/weave/traces?filter=..." \
  --pretty -o categories.yaml
```

3. **Annotate traces with discovered categories:**

```bash
weave analytics annotate "https://wandb.ai/your-team/your-project/weave/traces?filter=..." \
  --categories categories.yaml --pretty
```

4. **Summarize a single trace:**

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

### `weave analytics annotate`

Classify traces and add failure analysis annotations to Weave.

**Input:**
- A Weave URL containing traces to annotate (like `cluster`)
- A `categories.yaml` file with predefined categories (output from `cluster` command)

**Output:**
- Annotations added to traces in Weave with the assigned category
- JSON report with classification distribution

**Workflow:**

1. **Run `cluster` first** to discover failure categories and generate `categories.yaml`
2. **Run `annotate`** to classify traces and add annotations to Weave

**How it works:**

1. **Fetch traces** from the Weave API based on the URL filters
2. **Load categories** from the YAML file (generated by `cluster` command)
3. **Classify each trace** into one of the predefined categories using LLM
4. **Create AnnotationSpec** with enum of all categories and descriptive metadata
5. **Apply annotations** to each trace in Weave

**Options:**

| Option | Description |
|--------|-------------|
| `-c, --categories` | Path to categories YAML file (default: `categories.yaml`) |
| `--model` | LiteLLM model name |
| `--limit` | Maximum traces to annotate |
| `--max-concurrent` | Concurrent LLM calls (default: 10) |
| `--annotation-name` | Name for the annotation field (default: `failure_analysis`) |
| `--dry-run` | Preview classifications without making changes |
| `--pretty` | Pretty print with Rich formatting |
| `-o, --output` | Output file path |
| `--context` | User context about the AI system |

**Example workflow:**

```bash
# Step 1: Discover failure categories
weave analytics cluster "https://wandb.ai/team/project/weave/traces?..." \
  --pretty -o categories.yaml

# Step 2: Annotate traces with discovered categories
weave analytics annotate "https://wandb.ai/team/project/weave/traces?..." \
  --categories categories.yaml --pretty

# Preview before applying
weave analytics annotate "..." --dry-run --pretty
```

**Annotation in Weave UI:**

The command creates a Human Annotation scorer named "Failure Analysis" with:
- **Name**: "Failure Analysis"
- **Description**: References the weave analytics CLI, clustering date, and lists all category definitions
- **Field Schema**: String enum with all discovered categories

Annotations appear in the **Feedback** sidebar of trace details and the **Annotations** column in the traces table.

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

## URL Filtering

The CLI parses Weave trace URLs directly, including filters applied in the Weave UI. Simply copy the URL from your browser and pass it to the CLI commands.

**Supported URL parameters:**

| Parameter | Description | Example |
|-----------|-------------|---------|
| `filter` | Op version refs and basic filters | `{"opVersionRefs":["weave:///entity/project/op/MyOp:*"]}` |
| `filters` | Advanced filter items | `{"items":[{"field":"started_at","operator":"(date): before","value":"2025-04-21T22:00:00.000Z"}]}` |

**Supported filter operators:**

| Operator | Field Types | Example |
|----------|-------------|---------|
| `(string): equals` | Any string field | `op_name`, `display_name` |
| `(string): contains` | Any string field | Substring matching |
| `(string): in` | Any string field | Comma-separated values |
| `(bool): is` | Boolean fields | `true` / `false` |
| `(number): >` / `(number): <` | Numeric fields | `summary.usage.tokens` |
| `(date): before` / `(date): after` | Datetime fields | `started_at`, `ended_at` |

**How filtering works:**

1. **Op filtering** - `opVersionRefs` are passed directly to the Weave API's `filter.op_names` field, supporting wildcards like `:*`
2. **Date filtering** - ISO timestamps are converted to Unix timestamps and use the `$not`/`$gt` pattern per the [Weave API spec](https://docs.wandb.ai/weave/reference/service-api/calls/calls-query-stream)
3. **Root traces** - By default, only root traces (no parent) are fetched to avoid duplicate analysis

**Example with complex filters:**

```bash
# Filter by op name AND date range
weave analytics cluster "https://wandb.ai/team/project/weave/traces?\
filter={\"opVersionRefs\":[\"weave:///team/project/op/MyAgent.run:*\"]}&\
filters={\"items\":[{\"field\":\"started_at\",\"operator\":\"(date): before\",\"value\":\"2025-04-21T22:00:00.000Z\"}]}" \
--pretty
```

---

## Architecture

```
weave/analytics/
    main.py           - CLI entry point and command registration
    commands/
        setup.py      - Configuration wizard
        cluster.py    - Clustering command
        annotate.py   - Annotation command
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

