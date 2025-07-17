---
title: Weights & Biases MCP Server
---


:::tip[This is a notebook]

<a href="https://colab.research.google.com/github/wandb/weave/blob/master/docs/./notebooks/wandb_mcp_server.ipynb" target="_blank" rel="noopener noreferrer" class="navbar__item navbar__link button button--secondary button--med margin-right--sm notebook-cta-button"><div><img src="https://upload.wikimedia.org/wikipedia/commons/archive/d/d0/20221103151430%21Google_Colaboratory_SVG_Logo.svg" alt="Open In Colab" height="20px" /><div>Open in Colab</div></div></a>

<a href="https://github.com/wandb/weave/blob/master/docs/./notebooks/wandb_mcp_server.ipynb" target="_blank" rel="noopener noreferrer" class="navbar__item navbar__link button button--secondary button--med margin-right--sm notebook-cta-button"><div><img src="https://upload.wikimedia.org/wikipedia/commons/9/91/Octicons-mark-github.svg" alt="View in Github" height="15px" /><div>View in Github</div></div></a>

:::




# The Weights & Biases MCP Server

The W&B MCP Server enables AI assistants like Cursor, Windsurf, Claude Code and Claude Desktop to directly query and analyze your Weights & Biases data. This gives your AI coding assistant powerful capabilities to help you understand experiments, debug issues, and generate insights from your W&B Models and W&B Weave data.

:::note
The **[wandb MCP server documentation on GitHub](https://github.com/wandb/wandb-mcp-server/blob/main/README.md)** contains a fuller, in-depth guide on installation, available tools and troubleshooting.
:::

## Why use the W&B MCP Server?

When building AI applications, you often need to:
- Compare hyperparameters across experiment runs
- Analyze Weave evaluation traces to debug LLM applications  
- Create visualizations of training metrics
- Generate reports summarizing experiment results

The MCP server lets your AI assistant do all of this directly, without you having to manually copy data or write analysis code from scratch.

## Available tools

The server provides four main tools your AI assistant can use:

### `query_wandb_tool`
Query W&B experiment tracking data including runs, sweeps, and metrics. Your assistant can find the best performing models and compare metrics and hyperparameters across experiments.

### `query_weave_traces_tool`
Access Weave traces and evaluations for debugging LLM applications. Analyze latency, token usage, error rates, and trace through complex LLM workflows.

### `execute_sandbox_code_tool`
Run Python code in secure sandboxes to perform custom analysis, create visualizations, and process data. Supports both cloud (E2B) and local (Pyodide) execution environments.

### `create_wandb_report_tool`
Generate shareable W&B Reports with visualizations and analysis that you can share with your team.

## Quick start

1. Install the `uv` package manager:
   ```bash
   curl -LsSf https://astral.sh/uv/install.sh | sh
   ```

2. Get your W&B API key from [wandb.ai/authorize](https://wandb.ai/authorize)

3. Configure your AI assistant by adding the MCP server to its configuration file:
   ```json
   {
     "mcpServers": {
       "wandb": {
         "command": "uvx",
         "args": ["wandb-mcp-server"],
         "env": {
           "WANDB_API_KEY": "your-api-key"
         }
       }
     }
   }
   ```

4. Restart your AI assistant to load the server

### 1-line Quickstart helpers for Cursor, Windsurf, Claude and more

The [full wandb MCP server documentation on GitHub](https://github.com/wandb/wandb-mcp-server/blob/main/README.md) contains 1-line quickstart helpers for Cursor, Windsurf, Claude Code and Claude Desktop.

## Example queries

Once configured, you can ask your AI assistant questions like:

- "What are the top 5 runs by validation accuracy in my `dog-labs/pug-classification` project?"
- "Show me all Weave traces where latency exceeded 2 seconds in the last hour"
- "Create a scatter plot comparing learning rate vs final loss for all runs"
- "Generate a report summarizing the performance of different model architectures"

## Learn more

For detailed configuration options, sandbox setup, and troubleshooting, see the [full documentation on GitHub](https://github.com/wandb/wandb-mcp-server/blob/main/README.md).


```python

```
