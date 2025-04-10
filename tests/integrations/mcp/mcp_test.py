import asyncio
import tempfile
import os

import pytest

from weave.integrations.integration_utilities import (
    flatten_calls,
    flattened_calls_to_names,
)
from weave.trace.weave_client import WeaveClient
from weave.trace_server.trace_server_interface import CallsFilter

from mcp.server.fastmcp import FastMCP
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

def mcp_server():
    mcp = FastMCP("Demo")

    @mcp.tool()
    def add(a: int, b: int) -> int:
        return a + b
    
    @mcp.resource("greeting://{name}")
    def get_greeting(name: str) -> str:
        return f"Hello, {name}!"
    
    @mcp.prompt()
    def review_code(code: str) -> str:
        return f"Please review this code:\\n\\n{code}"
    
    return mcp


async def run_client():
    """Run the client and connect to the MCP server"""
    # Configure the server parameters
    server_params = StdioServerParameters(
        command="python",  # Executable
        args=["-c", "from integrations.mcp.mcp_test import mcp_server; mcp_server().run()"],  # Optional command line arguments
        env=None,  # Optional environment variables
    )

    # Connect to the server using stdio
    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            # Initialize the connection
            print("Initializing connection...")
            await session.initialize()
            print("Connection initialized successfully!")

            # List available tools
            tools = await session.list_tools()
            print(f"Available tools: {[tool.name for tool in tools.tools]}")

            # List resources
            resources = await session.list_resources()
            print(f"Available resources: {[resource.name for resource in resources.resources]}")

            # List prompts
            prompts = await session.list_prompts()
            print(f"Available prompts: {[prompt.name for prompt in prompts.prompts]}")

            # Call the add tool
            result = await session.call_tool("add", arguments={"a": 1, "b": 2})
            print(f"Result of add(1, 2): {result}")

            # Get a resource    
            resource = await session.read_resource("greeting://cw")
            print(f"Resource: {resource}")

            # Generate a prompt
            prompt = await session.get_prompt("review_code", arguments={"code": "print('Hello, world!')"})
            print(f"Prompt: {prompt}")


def main():
    """Main entry point"""
    
    asyncio.run(run_client())


@pytest.mark.skip_clickhouse_client
@pytest.mark.vcr(
    filter_headers=["authorization"],
    allowed_hosts=["api.wandb.ai", "localhost", "trace.wandb.ai"],
)
def test_mcp_client(client: WeaveClient) -> None:
    main()

    calls = list(client.calls(filter=CallsFilter(trace_roots_only=True)))
    assert len(calls) == 3

    flattened_calls = flatten_calls(calls)
    print("flattened_calls", flattened_calls)
    flattened_call_names = flattened_calls_to_names(flattened_calls)
    print("flattened_call_names", flattened_call_names)
    
    # Extract just the call names from the tuples (name, index)
    call_names = [name for name, _ in flattened_call_names]
    
    # Assert the expected call methods are present
    expected_call_names = [
        "mcp.client.session.ClientSession.call_tool.add",
        "mcp.client.session.ClientSession.read_resource",
        "mcp.client.session.ClientSession.get_prompt.review_code"
    ]
    
    for name in expected_call_names:
        assert any(name in call_name for call_name in call_names), f"Expected call {name} not found in calls"
    
    # Assert data within the calls
    call_tool_call = next(call for call, _ in flattened_calls if "call_tool.add" in call.op_name)
    print("call_tool_call", call_tool_call)
    
    # Access WeaveObject properties directly using attribute notation
    # The output appears to be another WeaveObject that wraps the data
    text_content = call_tool_call.output.content[0].text
    assert text_content == '3', "Expected add(1, 2) to return 3"
    
    resource_call = next(call for call, _ in flattened_calls if "read_resource" in call.op_name)
    text_content = resource_call.output.contents[0].text
    assert text_content == 'Hello, cw!', "Expected greeting to be 'Hello, cw!'"
    
    prompt_call = next(call for call, _ in flattened_calls if "get_prompt.review_code" in call.op_name)
    prompt_text = prompt_call.output.messages[0].content.text
    assert "Please review this code" in prompt_text, "Expected prompt to contain 'Please review this code'"
