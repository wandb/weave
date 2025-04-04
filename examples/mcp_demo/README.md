# MCP + Weave Integration Example

This example demonstrates a comprehensive integration between the Model Context Protocol (MCP) and Weave for tracing. It showcases how to instrument both the client and server components to capture detailed traces of their interactions.

## Features

This example demonstrates:

- Tools: Functions that can be called by clients
- Resources: Static and dynamic data that can be read by clients
- Prompts: Templated messages for consistent interactions

## Files

- `example_server.py`: A demo MCP server with various tools, resources, and prompts
- `example_client.py`: A client that connects to the server and provides a command-line interface to interact with all server capabilities

## Setup

1. Install the required dependencies:

```bash
uv pip install -e ".[mcp]"
```

2. No API keys are required for running this example

## Running the Example

```bash
uv run --no-refresh --frozen --no-sync --only-group "" --extra mcp examples/mcp_demo/example_client.py examples/mcp_demo/example_server.py
```

## Using the Interactive Client

The client provides a comprehensive command-line interface to interact with all server features:

- `tools` - List all available tools
- `resources` - List all available resources
- `prompts` - List all available prompts
- `add <a> <b>` - Add two numbers
- `bmi <weight_kg> <height_m>` - Calculate BMI
- `weather <city>` - Get weather for a city
- `greeting <name>` - Get personalized greeting
- `user <id>` - Get user profile
- `config` - Get application configuration
- `code-review <code>` - Get code review prompt
- `debug <error>` - Get debug error prompt
- `demo` - Run demos for all server features
- `quit` - Exit the session
