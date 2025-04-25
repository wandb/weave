# Model Context Protocol (MCP)

The Model Context Protocol (MCP) serves as a unified communication standard that enables AI applications to exchange information with Large Language Models (LLMs). Similar to how universal connectors revolutionized hardware connectivity, MCP promises to create a consistent interface for LLMs to access various data sources and interact with external tools, eliminating the need for custom integrations for each new service.

The weave integration allows you to trace your MCP Client and MCP Server. This integration provides detailed visibility into tool calls, resource access, and prompt generation within MCP-based systems.

:::Note
Currently our integration captures client-side and server-side operations separately, but does not provide visibility into their interaction. There's an ongoing proposal created by us to add OpenTelemetry trace support to MCP that would enable end-to-end observability - see [GitHub discussion #269](https://github.com/modelcontextprotocol/modelcontextprotocol/discussions/269).
:::

## What is MCP?

The Model Context Protocol (MCP) is an open protocol that standardizes how applications provide context to generative models (LLMs, VLMs, etc.).

MCP follows a client-server architecture where a host application can connect to multiple servers:

- **MCP Hosts**: Programs like Claude Desktop, IDEs, or AI tools that want to access data through MCP.
- **MCP Clients**: Protocol clients that maintain 1:1 connections with servers.
- **MCP Servers**: Lightweight programs that expose specific capabilities through the standardized protocol.
- **Data Sources**: Your computer's files, databases, services, or remote APIs that MCP servers can access.

MCP servers provide three main types of capabilities:

- **Tools**: Functions that can be called by clients
- **Resources**: Static and dynamic data that can be read by clients
- **Prompts**: Templated messages for consistent interactions

## Why need tracing ability?

As a developer you can fall in one of the three buckets:

- **MCP server-side developer**: You want to expose multiple tools, resources and prompts to the MCP client. You expose your existing application's tools, resources, etc. or you have built agents or have multiple agents orchestrated by an orchetrator agent. 

- **MCP client-side developer**: You might want to plug your client-side application to multiple MCP servers. A core part of your client-side logic is to make LLM calls to decide on which tool to be called or which resource to be fetched, etc.

- **MCP server and client developer**: You are developing both the server and the client.

If you fall into the first two bucket, you want to know which tool is called when, what is the execution flow, the token count, latency of different components in your server or client side logics and more. 

If you are developing both the server and client, the ability to see a unified trace timeline (we don't yet capture server-client interaction) can help you quickly iterate through both server and client side logic. 

With an observability layer you can:

- quickly iterate through your application
- audit the workflow or execution logic
- and identify bottlenecks.

## How the Weave Integration Works?

We automatically patch the key methods of [`mcp.server.fastmcp.FastMCP`](https://github.com/modelcontextprotocol/python-sdk/blob/b4c7db6a50a5c88bae1db5c1f7fba44d16eebc6e/src/mcp/server/fastmcp/server.py#L109) and [`mcp.ClientSession`](https://github.com/modelcontextprotocol/python-sdk/blob/b4c7db6a50a5c88bae1db5c1f7fba44d16eebc6e/src/mcp/client/session.py#L84) class with a [`weave.op()`](../tracking/ops.md) decorator.

We trace the following key components -- [**Tools**](https://modelcontextprotocol.io/docs/concepts/tools), [**Resources**](https://modelcontextprotocol.io/docs/concepts/resources), [**Prompts**](https://modelcontextprotocol.io/docs/concepts/prompts)

## Installation

To use the MCP integration with Weave, you'll need to install both weave and the MCP package:

```bash
pip install -qq mcp[cli] weave
```

## Quickstart Guide

### Prerequisites

Make sure you have both Weave and MCP installed as described in the Installation section.

### Using the Example Code

Weave includes ready-to-use MCP examples. Instead of creating files from scratch, you can use the examples provided in the Weave repository:

1. Clone the Weave repository if you haven't already:
   ```bash
   git clone https://github.com/wandb/weave
   cd weave
   ```

2. Install the required dependencies:
   ```bash
   pip install -e ".[mcp]"
   ```

3. Navigate to the MCP example directory:
   ```bash
   cd examples/mcp_demo
   ```

### Running the Example

The example consists of two main files:
- `example_server.py`: A demo MCP server with various tools, resources, and prompts
- `example_client.py`: A client that connects to the server

To run the example:

```bash
python example_client.py example_server.py
```

This will start the client, which will connect to and interact with the server. The client provides a command-line interface with the following options:

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
- `demo` - Run demos for all features
- `quit` - Exit the session

### Understanding the Example

#### Server-Side Code

The example server (`example_server.py`) defines:

1. **Tools**: Functions like `add()`, `calculate_bmi()`, and `fetch_weather()`
2. **Resources**: Data endpoints like `greeting://{name}`, `config://app`, and `users://{user_id}/profile`
3. **Prompts**: Templates like `review_code()` and `debug_error()`

All of these components are automatically traced by Weave, allowing you to monitor their usage, inputs, and outputs.

#### Client-Side Code

The example client (`example_client.py`) demonstrates:

1. How to connect to an MCP server
2. How to discover available tools, resources, and prompts
3. How to call tools with parameters
4. How to access resources with URIs
5. How to generate prompts with arguments

All client-side operations are also traced by Weave, creating a complete picture of the client-server interaction.

## Using the Integration

### Client-Side Integration

To enable tracing on an MCP client:

```python
import weave
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

# Initialize Weave
weave_client = weave.init("my-project")

# The MCP client operations will be automatically traced
async with stdio_client(server_params) as (read, write):
    async with ClientSession(read, write) as session:
        # Initialize the connection
        await session.initialize()
        
        # Call a tool (this will be traced)
        result = await session.call_tool("add", arguments={"a": 1, "b": 2})
        
        # Read a resource (this will be traced)
        resource = await session.read_resource("greeting://user")
        
        # Get a prompt (this will be traced)
        prompt = await session.get_prompt("review_code", 
                                        arguments={"code": "print('Hello')"})
```

### Server-Side Integration

To enable tracing on an MCP server:

```python
import weave
from mcp.server.fastmcp import FastMCP

# Initialize Weave
weave_client = weave.init("my-project")

# Create an MCP server
mcp = FastMCP("Demo")

# Define tools (will be traced)
@mcp.tool()
def add(a: int, b: int) -> int:
    """Add two numbers"""
    return a + b

# Define resources (will be traced)
@mcp.resource("greeting://{name}")
def get_greeting(name: str) -> str:
    """Get a personalized greeting"""
    return f"Hello, {name}!"

# Define prompts (will be traced)
@mcp.prompt()
def review_code(code: str) -> str:
    """Generate a code review prompt"""
    return f"Please review this code:\n\n{code}"

# Run the server
mcp.run(transport="stdio")
```

## Configuration

The MCP integration can be configured through environment variables:

- `MCP_TRACE_LIST_OPERATIONS`: Set to "true" to trace list operations (`list_tools`, `list_resources`, etc.)

## Further Resources

- [MCP Protocol Website](https://modelcontextprotocol.io)
- [MCP GitHub Organization](https://github.com/modelcontextprotocol)
- [Weave Documentation](https://docs.wandb.ai/weave)
- [Example MCP Applications](https://github.com/wandb/weave/tree/master/examples/mcp_demo)
