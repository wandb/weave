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

### 1. Setup credentials

```bash
weave analytics setup
```

This interactive wizard configures:
- **W&B API key** for fetching traces
- **LLM model** (default: `gemini/gemini-2.5-flash`)
- **LLM API key** for your chosen provider
- **Max sample size** (default: 500 traces) for large trace sets
- **Debug tracing** (optional) to inspect the analytics pipeline itself

### 2. Cluster traces from a Weave URL

Copy a trace URL from the Weave UI (including any filters) and run:

```bash
weave analytics cluster "https://wandb.ai/your-team/your-project/weave/traces?filter=..." \
  --context "Email agent for customer support" \
  --pretty \
  -o categories.yaml
```

For large trace sets (thousands of traces), the CLI automatically samples to stay within limits:

```bash
# Explicitly set sample size (overrides config)
weave analytics cluster "..." --sample-size 200 --pretty -o categories.yaml

# Disable sampling to process all traces
weave analytics cluster "..." --no-sampling --pretty -o categories.yaml
```

### 3. Annotate traces with discovered categories

Apply the discovered categories as annotations in Weave:

```bash
weave analytics annotate "https://wandb.ai/your-team/your-project/weave/traces?filter=..." \
  --categories categories.yaml \
  --sample-size 100 \
  --pretty
```

Annotations appear in the Weave UI's **Feedback** sidebar and **Annotations** column.

### 4. Summarize a single trace

```bash
weave analytics summarize "https://wandb.ai/your-team/your-project/weave/calls/abc123" --pretty
```

## Commands

### `weave analytics setup`

Interactive configuration wizard for setting up API keys and preferences.

**What it configures:**

- W&B API key (for fetching traces)
- LLM model and API key (for AI analysis)
- Max sample size (for scaling to large trace sets)
- Debug entity/project (optional, for tracing the analytics pipeline itself)

**Configuration storage:** `~/.weave/analytics_config`

**Options:**

| Option | Description |
|--------|-------------|
| `--wandb-api-key` | W&B API key |
| `--llm-model` | LiteLLM model name (default: `gemini/gemini-2.5-flash`) |
| `--llm-api-key` | API key for the LLM provider |
| `--llm-provider` | Provider: `google`, `openai`, `anthropic`, `wandb`, or `auto` |
| `--max-sample-size` | Max traces to sample (default: 500) |
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
| `--sample-size` | Override max sample size from config |
| `--no-sampling` | Disable sampling and process all traces |
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
| `--sample-size` | Override max sample size from config |
| `--no-sampling` | Disable sampling and process all traces |
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
| `--debug` | Enable Weave tracing for debugging |

---

## Deep Trace Analysis

The `--depth` option controls how many levels of nested traces (child calls) are fetched and analyzed.

### Default Depth Values

| Command | Default `--depth` | Behavior |
|---------|------------------|----------|
| `cluster` | **0** (disabled) | Only analyzes root traces by default for performance |
| `summarize` | **5** | Always fetches execution tree since single-trace analysis benefits from full context |

**Important:** A higher depth value retrieves **more** traces. For example, `--depth 5` fetches 5 levels deep (more traces), while `--depth 3` only fetches 3 levels (fewer traces).

### Enabling Deep Analysis for Clustering

For complex agentic workflows, enable deep trace analysis with the cluster command:

```bash
weave analytics cluster "..." --depth 5 --pretty
```

This fetches the full execution tree for each trace (nested function calls, tool invocations, etc.) and includes it in the analysis. The depth parameter controls how many levels of nested calls to include. The execution tree is automatically compacted if it exceeds token limits.

### Adjusting Depth for Summarize

By default, `summarize` fetches 5 levels deep. To limit or expand:

```bash
# Shallower analysis (faster, less context)
weave analytics summarize "..." --depth 2

# Deeper analysis (slower, more context)
weave analytics summarize "..." --depth 10
```

### When to Use Deep Analysis

Deep analysis is useful for:

- Multi-step agent workflows
- Traces with nested LLM calls
- Understanding failure cascades
- Debugging complex tool orchestration

---

## Debug Mode

To trace the analytics pipeline itself (useful for debugging or understanding how the commands work):

```bash
# Debug clustering
weave analytics cluster "..." --debug

# Debug summarization
weave analytics summarize "..." --debug
```

This logs all LLM calls to your configured debug Weave project, allowing you to inspect the prompts and responses used for categorization or summarization.

**Setup:** Configure your debug project during `weave analytics setup` or set `DEBUG_ENTITY` and `DEBUG_PROJECT` in the config file (`~/.weave/analytics_config`).

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

### File Structure

```
weave/analytics/
├── main.py           - CLI entry point and command registration
├── commands/
│   ├── setup.py      - Configuration wizard
│   ├── cluster.py    - Clustering command
│   ├── annotate.py   - Annotation command
│   └── summarize.py  - Summarization command
├── clustering.py     - Core clustering pipeline and progress tracking
├── models.py         - Pydantic models for structured outputs
├── prompts.py        - LLM prompts for categorization
├── url_parser.py     - Weave URL parsing utilities
├── weave_client.py   - Weave API client wrapper
├── header.py         - CLI branding
└── spinner.py        - Loading spinner utility
```

### Clustering Workflow

The clustering pipeline follows a multi-stage approach to discover and assign categories:

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           CLUSTERING PIPELINE                                │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  1. FETCH & SAMPLE                                                           │
│     ┌──────────────┐    ┌──────────────┐    ┌──────────────┐                │
│     │ Parse URL &  │───▶│ Count Total  │───▶│ Random Sample│                │
│     │ Filters      │    │ Traces       │    │ (if needed)  │                │
│     └──────────────┘    └──────────────┘    └──────────────┘                │
│                                                     │                        │
│                                                     ▼                        │
│  2. DEEP TRACE ANALYSIS (optional, --depth N)                                │
│     ┌──────────────────────────────────────────────────────┐                │
│     │ Fetch execution trees for each trace (nested calls)  │                │
│     │ Progress: [████████████████████] 50/50 traces        │                │
│     └──────────────────────────────────────────────────────┘                │
│                                                     │                        │
│                                                     ▼                        │
│  3. DRAFT CATEGORIZATION (concurrent LLM calls)                              │
│     ┌──────────────────────────────────────────────────────┐                │
│     │ Each trace → LLM → 1-3 candidate categories          │                │
│     │ Progress: [████████████████████] 50/50 traces        │                │
│     │ Current: abc123-def456-789...                        │                │
│     └──────────────────────────────────────────────────────┘                │
│                                                     │                        │
│                                                     ▼                        │
│  4. CLUSTER AGGREGATION (single LLM call)                                    │
│     ┌──────────────────────────────────────────────────────┐                │
│     │ Merge similar categories into coherent clusters      │                │
│     │ e.g., "timeout", "api_timeout" → "timeout_errors"    │                │
│     └──────────────────────────────────────────────────────┘                │
│                                                     │                        │
│                                                     ▼                        │
│  5. FINAL CLASSIFICATION (concurrent LLM calls)                              │
│     ┌──────────────────────────────────────────────────────┐                │
│     │ Each trace → LLM → Final category assignment         │                │
│     │ Progress: [████████████████████] 50/50 traces        │                │
│     │ Current: xyz789-abc012-345...                        │                │
│     └──────────────────────────────────────────────────────┘                │
│                                                     │                        │
│                                                     ▼                        │
│  OUTPUT: categories.yaml + JSON report                                       │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Annotation Workflow

The annotation command applies pre-discovered categories to traces:

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                          ANNOTATION PIPELINE                                 │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  1. LOAD CATEGORIES                                                          │
│     ┌──────────────┐                                                        │
│     │ Parse YAML   │  categories.yaml from cluster command                  │
│     │ File         │                                                        │
│     └──────────────┘                                                        │
│             │                                                                │
│             ▼                                                                │
│  2. FETCH & SAMPLE TRACES                                                    │
│     ┌──────────────┐    ┌──────────────┐    ┌──────────────┐                │
│     │ Parse URL    │───▶│ Count Total  │───▶│ Random Sample│                │
│     │              │    │ (API stats)  │    │ (if needed)  │                │
│     └──────────────┘    └──────────────┘    └──────────────┘                │
│                                                     │                        │
│                                                     ▼                        │
│  3. CLASSIFY TRACES (concurrent LLM calls)                                   │
│     ┌──────────────────────────────────────────────────────┐                │
│     │ Each trace → LLM → Category from predefined set      │                │
│     │ Progress: [████████████████████] 100/100 traces      │                │
│     │ Current: trace-id-being-processed...                 │                │
│     └──────────────────────────────────────────────────────┘                │
│                                                     │                        │
│                                                     ▼                        │
│  4. CREATE ANNOTATION SPEC                                                   │
│     ┌──────────────────────────────────────────────────────┐                │
│     │ Create/update Human Annotation scorer in Weave       │                │
│     │ with enum of all category names                      │                │
│     └──────────────────────────────────────────────────────┘                │
│                                                     │                        │
│                                                     ▼                        │
│  5. APPLY ANNOTATIONS                                                        │
│     ┌──────────────────────────────────────────────────────┐                │
│     │ Add feedback to each trace with assigned category    │                │
│     │ Visible in Weave UI Feedback sidebar                 │                │
│     └──────────────────────────────────────────────────────┘                │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Sampling for Scalability

When working with large trace sets (thousands of traces), the CLI implements intelligent sampling:

1. **Count Phase**: Uses the `/calls/query_stats` API endpoint to efficiently get total trace count
2. **ID Fetch**: Fetches only trace IDs (lightweight) for the full filtered set
3. **Random Sample**: Randomly selects up to `MAX_SAMPLE_SIZE` traces
4. **Full Fetch**: Fetches complete trace data only for sampled traces

This approach ensures:
- **Efficiency**: Avoids fetching full data for thousands of traces
- **Representativeness**: Random sampling gives statistically meaningful results
- **Configurability**: Sample size can be set via `setup`, `--sample-size`, or disabled with `--no-sampling`

```bash
# Configure default sample size during setup
weave analytics setup
# → "Max sample size (default 500):"

# Override per-command
weave analytics cluster "..." --sample-size 200

# Disable sampling for complete analysis
weave analytics cluster "..." --no-sampling
```

### Progress Tracking

Long-running operations display real-time progress with:

- **Progress bar**: Visual indication of completion percentage
- **Trace counter**: Current trace number out of total
- **Current trace ID**: Shows which trace is being processed (truncated for readability)
- **Phase indicators**: Clear labels for each pipeline stage

Example output:
```
Sampling 100 of 1876 traces (5.3%)
Fetching Traces        [████████████████████] 100/100 done
Resolving References   [████████████████████] 100/100 done
Classifying Traces     [████████████████░░░░]  82/100 abc123-def456-789...
```

---

## Supported LLM Providers

Via LiteLLM, the following providers are supported:

| Provider | Model format | Environment variable |
|----------|-------------|---------------------|
| Google (default) | `gemini/gemini-2.5-flash` | `GOOGLE_API_KEY` |
| OpenAI | `openai/gpt-4o` | `OPENAI_API_KEY` |
| Anthropic | `anthropic/claude-3-5-sonnet` | `ANTHROPIC_API_KEY` |
| **W&B Inference** | `wandb/meta-llama/Llama-3.1-8B-Instruct` | `WANDB_API_KEY` |

### W&B Inference

[W&B Inference](https://docs.wandb.ai/inference) gives you access to leading open-source foundation models through an OpenAI-compatible API. Since you already have a `WANDB_API_KEY` configured for fetching traces, no additional API key setup is needed.

**Available models include:**
- `wandb/meta-llama/Llama-3.1-8B-Instruct`
- `wandb/meta-llama/Llama-3.1-70B-Instruct`
- And more at [wandb.ai/inference](https://wandb.ai/inference)

**Example:**

```bash
weave analytics cluster "https://wandb.ai/team/project/weave/traces?..." \
  --model "wandb/meta-llama/Llama-3.1-8B-Instruct" --pretty
```

See [LiteLLM documentation](https://docs.litellm.ai/docs/providers) for additional providers.

---

## Tips

- **Start with `--pretty`** for interactive use to see progress and formatted output
- **Use `--limit`** when exploring large trace sets to reduce cost and time
- **Provide `--context`** to help the LLM understand your specific use case
- **Use `--depth N`** for agentic workflows where nested execution matters
- **Pipe to jq** for JSON processing: `weave analytics cluster "..." | jq '.clusters[0]'`

