import asyncio

import pytest
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from mcp.server.fastmcp import FastMCP

from weave.integrations.integration_utilities import (
    flatten_calls,
    flattened_calls_to_names,
)
from weave.trace.weave_client import WeaveClient
from weave.trace_server.trace_server_interface import CallsFilter


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
        command="python",
        args=[
            "-c",
            "from integrations.mcp.mcp_test import mcp_server; mcp_server().run()",
        ],
        env=None,
    )

    # Connect to the server using stdio
    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            # Initialize the connection
            await session.initialize()
            print("Connection initialized successfully!")

            # List available tools
            tools = await session.list_tools()
            print(f"Available tools: {[tool.name for tool in tools.tools]}")

            # List resources
            resources = await session.list_resources()
            print(
                f"Available resources: {[resource.name for resource in resources.resources]}"
            )

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
            prompt = await session.get_prompt(
                "review_code", arguments={"code": "print('Hello, world!')"}
            )
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
    flattened_call_names = flattened_calls_to_names(flattened_calls)

    call_names = [name for name, _ in flattened_call_names]
    expected_call_names = [
        "mcp.client.session.ClientSession.call_tool.add",
        "mcp.client.session.ClientSession.read_resource",
        "mcp.client.session.ClientSession.get_prompt.review_code",
    ]

    for name in expected_call_names:
        assert any(
            name in call_name for call_name in call_names
        ), f"Expected call {name} not found in calls"

    # Assert data within the calls
    call_tool_call = next(
        call for call, _ in flattened_calls if "call_tool.add" in call.op_name
    )
    print("call_tool_call", call_tool_call)

    # outputs
    text_content = call_tool_call.output.content[0].text
    assert text_content == "3", "Expected add(1, 2) to return 3"

    resource_call = next(
        call for call, _ in flattened_calls if "read_resource" in call.op_name
    )
    text_content = resource_call.output.contents[0].text
    assert text_content == "Hello, cw!", "Expected greeting to be 'Hello, cw!'"

    prompt_call = next(
        call for call, _ in flattened_calls if "get_prompt.review_code" in call.op_name
    )
    prompt_text = prompt_call.output.messages[0].content.text
    assert (
        "Please review this code" in prompt_text
    ), "Expected prompt to contain 'Please review this code'"


@pytest.mark.skip_clickhouse_client
@pytest.mark.vcr(
    filter_headers=["authorization"],
    allowed_hosts=["api.wandb.ai", "localhost", "trace.wandb.ai"],
)
def test_mcp_server(client: WeaveClient) -> None:
    fastmcp = mcp_server()
    
    result = asyncio.run(fastmcp.call_tool("add", {"a": 1, "b": 2}))
    resource = asyncio.run(fastmcp.read_resource("greeting://cw"))
    prompt = asyncio.run(fastmcp.get_prompt("review_code", {"code": "print('Hello, world!')"}))

    assert result[0].text == str(3)
    assert resource[0].content == "Hello, cw!"
    assert prompt.messages[0].content.text == "Please review this code:\\n\\nprint('Hello, world!')"

    calls = list(client.calls(filter=CallsFilter(trace_roots_only=True)))
    assert len(calls) == 3

    flattened_calls = flatten_calls(calls)
    print(len(flattened_calls))
    
    call_0, _ = flattened_calls[0]
    assert call_0._display_name == "FastMCP.call_tool"
    inputs = call_0.inputs
    assert inputs["name"] == "add"
    assert inputs["arguments"]["a"] == 1
    assert inputs["arguments"]["b"] == 2
    assert call_0.started_at < call_0.ended_at

    outputs = call_0.output[0]
    assert outputs._class_name == "TextContent"
    assert outputs.text == "3"   

    call_1, _ = flattened_calls[1]
    assert call_1._display_name == "add"
    assert call_1.started_at < call_1.ended_at
    
    call_2, _ = flattened_calls[2]
    assert call_2._display_name == "FastMCP.read_resource"
    assert call_2.inputs["uri"] == "greeting://cw"
    assert call_2.output[0].content == "Hello, cw!"
    assert call_2.started_at < call_2.ended_at

    call_3, _ = flattened_calls[3]
    assert call_3._display_name == "get_greeting"
    assert call_3.started_at < call_3.ended_at

    call_4, _ = flattened_calls[4]
    print(call_4)
    assert call_4._display_name == "review_code"
    assert call_4.inputs["code"] == "print('Hello, world!')"
    assert call_4.output == "Please review this code:\\n\\nprint('Hello, world!')"
    assert call_4.started_at < call_4.ended_at
