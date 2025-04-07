import asyncio
import sys
from contextlib import AsyncExitStack
from typing import Any, Dict, Optional

# import weave
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from mcp.types import TextContent
from pydantic import AnyUrl

# Initialize Weave for tracing
# weave_client = weave.init("mcp_example")
# print(f"Weave initialized: {weave_client}")


class MCPClient:
    def __init__(self):
        # Initialize session and client objects
        self.session: Optional[ClientSession] = None
        self.exit_stack = AsyncExitStack()

    # @weave.op()
    async def connect_to_server(self, server_script_path: str):
        """Connect to an MCP server

        Args:
            server_script_path: Path to the server script (.py or .js)
        """
        print(f"Connecting to server at: {server_script_path}")

        server_params = StdioServerParameters(
            command="python", args=[server_script_path], env=None
        )

        stdio_transport = await self.exit_stack.enter_async_context(
            stdio_client(server_params)
        )
        self.stdio, self.write = stdio_transport
        self.session = await self.exit_stack.enter_async_context(
            ClientSession(self.stdio, self.write)
        )

        await self.session.initialize()

        # List available tools
        tools_response = await self.session.list_tools()
        print("\nAvailable tools:", [tool.name for tool in tools_response.tools])

        # List available resources
        resources_response = await self.session.list_resources()
        print(
            "Available resources:",
            [resource.uri for resource in resources_response.resources],
        )

        # List available prompts
        prompts_response = await self.session.list_prompts()
        print(
            "Available prompts:", [prompt.name for prompt in prompts_response.prompts]
        )

        print("\nServer connection established!")
        return {
            "tools": tools_response.tools,
            "resources": resources_response.resources,
            "prompts": prompts_response.prompts,
        }

    # @weave.op()
    async def call_tool(self, tool_name: str, arguments: Dict[str, Any]):
        """Call a tool on the MCP server

        Args:
            tool_name: Name of the tool to call
            arguments: Arguments to pass to the tool
        """
        if not self.session:
            raise RuntimeError(
                "Not connected to a server. Call connect_to_server first."
            )

        # with weave.attributes({"mcp_component": "client", "mcp_method": "call_tool", "tool": tool_name}):
        print(f"Calling tool: {tool_name} with arguments: {arguments}")
        result = await self.session.call_tool(tool_name, arguments)
        content = result.content
        if (
            isinstance(content, list)
            and len(content) > 0
            and isinstance(content[0], TextContent)
        ):
            return content[0].text
        return content

    # @weave.op()
    async def read_resource(self, uri: str):
        """Read a resource from the MCP server

        Args:
            uri: URI of the resource to read
        """
        if not self.session:
            raise RuntimeError(
                "Not connected to a server. Call connect_to_server first."
            )

        # with weave.attributes({"mcp_component": "client", "mcp_method": "read_resource", "uri": uri}):
        print(f"Reading resource: {uri}")
        result = await self.session.read_resource(AnyUrl(uri))
        return result

    # @weave.op()
    async def get_prompt(self, prompt_name: str, arguments: Dict[str, str] = None):
        """Get a prompt from the MCP server

        Args:
            prompt_name: Name of the prompt to get
            arguments: Arguments to pass to the prompt
        """
        if not self.session:
            raise RuntimeError(
                "Not connected to a server. Call connect_to_server first."
            )

        # with weave.attributes({"mcp_component": "client", "mcp_method": "get_prompt", "prompt": prompt_name}):
        print(f"Getting prompt: {prompt_name} with arguments: {arguments}")
        result = await self.session.get_prompt(prompt_name, arguments)
        return result.messages

    # @weave.op()
    async def demo_all_tools(self):
        """Demonstrate all available tools"""
        if not self.session:
            raise RuntimeError(
                "Not connected to a server. Call connect_to_server first."
            )

        print("\n=== TOOL DEMO ===")
        tools_response = await self.session.list_tools()

        results = []
        for tool in tools_response.tools:
            try:
                name = tool.name
                print(f"\nDemonstrating tool: {name}")
                print(f"Description: {tool.description}")

                if name == "add":
                    result = await self.call_tool("add", {"a": 5, "b": 7})
                    print(f"Result of adding 5 + 7: {result}")
                    results.append({"name": name, "result": result})

                elif name == "calculate_bmi":
                    result = await self.call_tool(
                        "calculate_bmi", {"weight_kg": 70, "height_m": 1.75}
                    )
                    print(f"BMI for 70kg/1.75m: {result}")
                    results.append({"name": name, "result": result})

                elif name == "fetch_weather":
                    try:
                        result = await self.call_tool(
                            "fetch_weather", {"city": "San Francisco"}
                        )
                        print(f"Weather for San Francisco: {result}")
                        results.append({"name": name, "result": result})
                    except Exception as e:
                        print(f"Weather API error (expected in demo): {e}")
                        results.append({"name": name, "error": str(e)})

                elif name == "create_thumbnail":
                    image = await self.call_tool("create_thumbnail", {})
                    print(f"Thumbnail: {image}")
                    results.append({"name": name, "result": image})

            except Exception as e:
                print(f"Error with {name}: {e}")
                results.append({"name": name, "error": str(e)})

        return results

    # @weave.op()
    async def demo_all_resources(self):
        """Demonstrate all available resources"""
        if not self.session:
            raise RuntimeError(
                "Not connected to a server. Call connect_to_server first."
            )

        print("\n=== RESOURCE DEMO ===")
        resources_response = await self.session.list_resources()

        results = []
        # Fixed resources
        try:
            config = await self.read_resource("config://app")
            print(f"App Configuration: {config}")
            results.append({"uri": "config://app", "content": config})
        except Exception as e:
            print(f"Error reading config: {e}")
            results.append({"uri": "config://app", "error": str(e)})

        # Dynamic resources with parameters
        try:
            greeting = await self.read_resource("greeting://Alice")
            print(f"Greeting: {greeting}")
            results.append({"uri": "greeting://Alice", "content": greeting})
        except Exception as e:
            print(f"Error reading greeting: {e}")
            results.append({"uri": "greeting://Alice", "error": str(e)})

        try:
            profile = await self.read_resource("users://123/profile")
            print(f"User Profile: {profile}")
            results.append({"uri": "users://123/profile", "content": profile})
        except Exception as e:
            print(f"Error reading profile: {e}")
            results.append({"uri": "users://123/profile", "error": str(e)})

        return results

    # @weave.op()
    async def demo_all_prompts(self):
        """Demonstrate all available prompts"""
        if not self.session:
            raise RuntimeError(
                "Not connected to a server. Call connect_to_server first."
            )

        print("\n=== PROMPT DEMO ===")
        prompts_response = await self.session.list_prompts()

        results = []
        for prompt in prompts_response.prompts:
            try:
                name = prompt.name
                print(f"\nDemonstrating prompt: {name}")

                if name == "review_code":
                    result = await self.get_prompt(
                        "review_code", {"code": "def hello(): print('Hello World')"}
                    )
                    print(f"Code review prompt: {result}")
                    results.append({"name": name, "result": result})

                elif name == "debug_error":
                    result = await self.get_prompt(
                        "debug_error", {"error": "NameError: name 'x' is not defined"}
                    )
                    print(f"Debug error prompt: {result}")
                    results.append({"name": name, "result": result})

            except Exception as e:
                print(f"Error with {name}: {e}")
                results.append({"name": name, "error": str(e)})

        return results

    # @weave.op()
    async def interactive_session(self):
        """Run an interactive session to use MCP tools and resources"""
        if not self.session:
            raise RuntimeError(
                "Not connected to a server. Call connect_to_server first."
            )

        print("\nMCP Interactive Session")
        print("Available commands:")
        print("  tools - List all available tools")
        print("  resources - List all available resources")
        print("  prompts - List all available prompts")
        print("  add <a> <b> - Add two numbers")
        print("  bmi <weight_kg> <height_m> - Calculate BMI")
        print("  weather <city> - Get weather for a city")
        print("  greeting <name> - Get personalized greeting")
        print("  user <id> - Get user profile")
        print("  config - Get application configuration")
        print("  code-review <code> - Get code review prompt")
        print("  debug <error> - Get debug error prompt")
        print("  create_thumbnail - Create a thumbnail")
        print("  demo - Run demos for all features")
        print("  q - Exit the session")

        while True:
            try:
                command = input("\nCommand: ").strip()

                if command.lower() == "q":
                    break

                parts = command.split()
                if not parts:
                    continue

                cmd = parts[0].lower()

                if cmd == "tools":
                    tools_response = await self.session.list_tools()
                    print("\nAvailable tools:")
                    for tool in tools_response.tools:
                        print(f"  {tool.name}: {tool.description}")

                elif cmd == "resources":
                    resources_response = await self.session.list_resources()
                    print("\nAvailable resources:")
                    for resource in resources_response.resources:
                        print(f"  {resource.uri}: {resource.description}")

                elif cmd == "prompts":
                    prompts_response = await self.session.list_prompts()
                    print("\nAvailable prompts:")
                    for prompt in prompts_response.prompts:
                        print(f"  {prompt.name}: {prompt.description}")
                        if prompt.arguments:
                            print("    Arguments:")
                            for arg in prompt.arguments:
                                print(
                                    f"      {arg.name}: {arg.description} ({'required' if arg.required else 'optional'})"
                                )

                elif cmd == "add" and len(parts) == 3:
                    try:
                        a = int(parts[1])
                        b = int(parts[2])
                        result = await self.call_tool("add", {"a": a, "b": b})
                        print(f"\nResult: {a} + {b} = {result}")
                    except ValueError:
                        print("Error: Arguments must be integers")

                elif cmd == "bmi" and len(parts) == 3:
                    try:
                        weight = float(parts[1])
                        height = float(parts[2])
                        result = await self.call_tool(
                            "calculate_bmi", {"weight_kg": weight, "height_m": height}
                        )
                        print(f"\nBMI for {weight}kg/{height}m: {result}")
                    except ValueError:
                        print("Error: Arguments must be numbers")

                elif cmd == "weather" and len(parts) == 2:
                    city = parts[1]
                    try:
                        result = await self.call_tool("fetch_weather", {"city": city})
                        print(f"\nWeather for {city}: {result}")
                    except Exception as e:
                        print(f"Error fetching weather: {e}")

                elif cmd == "greeting" and len(parts) == 2:
                    name = parts[1]
                    try:
                        result = await self.read_resource(f"greeting://{name}")
                        print(f"\nGreeting: {result.contents[0].text}")
                    except Exception as e:
                        print(f"Error reading greeting: {e}")

                elif cmd == "user" and len(parts) == 2:
                    user_id = parts[1]
                    try:
                        result = await self.read_resource(f"users://{user_id}/profile")
                        print(f"\nUser Profile: {result.contents[0].text}")
                    except Exception as e:
                        print(f"Error reading user profile: {e}")

                elif cmd == "config":
                    try:
                        result = await self.read_resource("config://app")
                        print(f"\nApp Configuration: {result.contents[0].text}")
                    except Exception as e:
                        print(f"Error reading config: {e}")

                elif cmd == "code-review" and len(parts) >= 2:
                    code = " ".join(parts[1:])
                    try:
                        result = await self.get_prompt("review_code", {"code": code})
                        print(f"\nCode Review Prompt: {result}")
                    except Exception as e:
                        print(f"Error getting prompt: {e}")

                elif cmd == "debug" and len(parts) >= 2:
                    error = " ".join(parts[1:])
                    try:
                        result = await self.get_prompt("debug_error", {"error": error})
                        print(f"\nDebug Error Prompt: {result}")
                    except Exception as e:
                        print(f"Error getting prompt: {e}")

                elif cmd == "create_thumbnail":
                    image = await self.call_tool("create_thumbnail", {})
                    print(f"Thumbnail: {image}")

                elif cmd == "demo":
                    print("\nRunning full demo...")
                    await self.demo_all_tools()
                    await self.demo_all_resources()
                    await self.demo_all_prompts()

                else:
                    print("Unknown command or invalid arguments")

            except Exception as e:
                print(f"Error: {str(e)}")

    async def cleanup(self):
        """Clean up resources"""
        await self.exit_stack.aclose()


# @weave.op()
async def run_client(server_path: str):
    """Run the MCP client and connect to the specified server"""
    client = MCPClient()
    try:
        await client.connect_to_server(server_path)
        await client.interactive_session()
    finally:
        await client.cleanup()


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: uv run example_client.py <path_to_server_script>")
        sys.exit(1)

    server_script_path = sys.argv[1]
    asyncio.run(run_client(server_script_path))
