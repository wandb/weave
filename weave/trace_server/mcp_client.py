"""MCP (Model Context Protocol) client for fetching and executing tools.

This module provides functionality to:
1. Connect to MCP servers over HTTP
2. Fetch available tools from MCP servers
3. Execute tool calls and return results

MCP Specification: https://modelcontextprotocol.io/
"""

import json
import logging
from typing import Any

import httpx
from pydantic import BaseModel

from weave.trace_server import trace_server_interface as tsi
from weave.trace_server.secret_fetcher_context import _secret_fetcher_context

logger = logging.getLogger(__name__)

# Default timeout for MCP HTTP requests
MCP_REQUEST_TIMEOUT = 30.0


class MCPError(Exception):
    """Base exception for MCP-related errors."""

    pass


class MCPConnectionError(MCPError):
    """Error connecting to an MCP server."""

    pass


class MCPToolExecutionError(MCPError):
    """Error executing an MCP tool."""

    pass


class MCPToolResult(BaseModel):
    """Result from executing an MCP tool."""

    tool_call_id: str
    server_name: str
    tool_name: str
    result: Any
    error: str | None = None


def _get_mcp_headers(server: tsi.MCPServerConfig) -> dict[str, str]:
    """Get all headers for an MCP server request.

    Combines custom headers from config with Authorization header from secret.

    Args:
        server: The MCP server configuration

    Returns:
        Dictionary containing all headers for the request
    """
    headers: dict[str, str] = {}

    # Add custom headers from config first
    if server.headers:
        headers.update(server.headers)

    # Add Authorization header from secret if configured
    if server.api_key_secret:
        secret_fetcher = _secret_fetcher_context.get()
        if not secret_fetcher:
            logger.warning(
                f"No secret fetcher available for MCP server {server.name}, "
                "proceeding without authentication"
            )
        else:
            fetch_result = secret_fetcher.fetch(server.api_key_secret)
            secrets = {}
            if fetch_result:
                secrets = fetch_result.get("secrets", {})
            api_key = secrets.get(server.api_key_secret)

            if api_key:
                headers["Authorization"] = f"Bearer {api_key}"
            else:
                logger.warning(
                    f"API key secret '{server.api_key_secret}' not found for MCP server {server.name}"
                )

    return headers


def fetch_mcp_tools(
    servers: list[tsi.MCPServerConfig],
) -> tuple[list[tsi.MCPTool], list[str]]:
    """Fetch tools from multiple MCP servers.

    Args:
        servers: List of MCP server configurations

    Returns:
        Tuple of (tools, errors) where tools is a list of MCPTool objects
        and errors is a list of error messages for servers that failed

    Examples:
        >>> servers = [MCPServerConfig(name="local", url="http://localhost:3000/mcp")]
        >>> tools, errors = fetch_mcp_tools(servers)
        >>> for tool in tools:
        ...     print(f"{tool.server_name}: {tool.name}")
    """
    all_tools: list[tsi.MCPTool] = []
    errors: list[str] = []

    for server in servers:
        if not server.enabled:
            continue

        try:
            tools = _fetch_tools_from_server(server)
            all_tools.extend(tools)
        except MCPError as e:
            error_msg = f"Failed to fetch tools from MCP server '{server.name}': {e}"
            logger.error(error_msg)
            errors.append(error_msg)
        except Exception as e:
            error_msg = (
                f"Unexpected error fetching tools from MCP server '{server.name}': {e}"
            )
            logger.error(error_msg, exc_info=True)
            errors.append(error_msg)

    return all_tools, errors


def _parse_sse_response(response_text: str) -> dict:
    """Parse Server-Sent Events (SSE) response format.

    SSE format:
        event: message
        data: {"jsonrpc": "2.0", ...}

    Args:
        response_text: The raw SSE response text

    Returns:
        Parsed JSON data from the SSE event
    """
    result = {}
    for line in response_text.strip().split("\n"):
        if line.startswith("data:"):
            data_str = line[5:].strip()
            if data_str:
                try:
                    result = json.loads(data_str)
                except json.JSONDecodeError:
                    continue
    return result


def _fetch_tools_from_server(server: tsi.MCPServerConfig) -> list[tsi.MCPTool]:
    """Fetch tools from a single MCP server.

    Args:
        server: The MCP server configuration

    Returns:
        List of tools from the server
    """
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json, text/event-stream",
        **_get_mcp_headers(server),
    }

    # MCP uses JSON-RPC 2.0 protocol
    request_body = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/list",
        "params": {},
    }

    try:
        with httpx.Client(timeout=MCP_REQUEST_TIMEOUT) as client:
            response = client.post(
                server.url,
                headers=headers,
                json=request_body,
            )
            response.raise_for_status()
    except httpx.ConnectError as e:
        raise MCPConnectionError(f"Could not connect to {server.url}: {e}") from e
    except httpx.TimeoutException as e:
        raise MCPConnectionError(f"Timeout connecting to {server.url}: {e}") from e
    except httpx.HTTPStatusError as e:
        # Try to get error details from response body
        error_detail = ""
        try:
            error_body = e.response.json()
            error_detail = f": {error_body.get('message', error_body.get('error', ''))}"
        except Exception:
            try:
                error_detail = f": {e.response.text[:200]}"
            except Exception:
                pass
        raise MCPConnectionError(
            f"HTTP error from {server.url}: {e.response.status_code}{error_detail}"
        ) from e

    # Check content type to determine how to parse response
    content_type = response.headers.get("content-type", "")
    response_text = response.text

    # Log response for debugging
    logger.debug(
        f"MCP response from {server.name}: content-type={content_type}, "
        f"length={len(response_text)}, preview={response_text[:200] if response_text else 'empty'}"
    )

    if not response_text or not response_text.strip():
        raise MCPError(f"Empty response from {server.url}")

    # Try to parse as JSON first
    result = None

    # Handle SSE format (text/event-stream)
    if "text/event-stream" in content_type:
        result = _parse_sse_response(response_text)
    else:
        try:
            result = response.json()
        except json.JSONDecodeError:
            # Try SSE parsing as fallback (some servers send SSE with wrong content-type)
            result = _parse_sse_response(response_text)

    if not result:
        raise MCPError(
            f"Could not parse response from {server.url}. "
            f"Content-Type: {content_type}, Response: {response_text[:500]}"
        )

    # Check for JSON-RPC error
    if "error" in result:
        error = result["error"]
        raise MCPError(
            f"MCP error from {server.name}: {error.get('message', 'Unknown error')}"
        )

    # Extract tools from result
    tools_data = result.get("result", {}).get("tools", [])

    tools = []
    for tool_data in tools_data:
        tool = tsi.MCPTool(
            name=tool_data.get("name", ""),
            description=tool_data.get("description"),
            input_schema=tool_data.get("inputSchema"),
            server_name=server.name,
        )
        tools.append(tool)

    return tools


def convert_mcp_tools_to_openai_format(
    mcp_tools: list[tsi.MCPTool],
) -> list[dict[str, Any]]:
    """Convert MCP tools to OpenAI function calling format.

    Args:
        mcp_tools: List of MCP tools

    Returns:
        List of tools in OpenAI format for use with LiteLLM

    Examples:
        >>> tools = [MCPTool(name="get_weather", description="Get weather", server_name="local")]
        >>> openai_tools = convert_mcp_tools_to_openai_format(tools)
    """
    openai_tools = []

    for tool in mcp_tools:
        openai_tool = {
            "type": "function",
            "function": {
                "name": f"{tool.server_name}__{tool.name}",
                "description": tool.description or f"Tool: {tool.name}",
                "parameters": tool.input_schema
                or {"type": "object", "properties": {}},
            },
        }
        openai_tools.append(openai_tool)

    return openai_tools


def execute_mcp_tool_calls(
    tool_calls: list[dict[str, Any]],
    servers: list[tsi.MCPServerConfig],
    mcp_tools: list[tsi.MCPTool],
) -> list[MCPToolResult]:
    """Execute MCP tool calls and return results.

    Args:
        tool_calls: List of tool calls from the LLM response
        servers: List of MCP server configurations
        mcp_tools: List of available MCP tools (for server lookup)

    Returns:
        List of MCPToolResult objects containing the results or errors

    Examples:
        >>> tool_calls = [{"id": "call_1", "function": {"name": "local__get_weather", "arguments": "{}"}}]
        >>> results = execute_mcp_tool_calls(tool_calls, servers, mcp_tools)
    """
    results: list[MCPToolResult] = []

    # Build a map from tool name to server
    server_map: dict[str, tsi.MCPServerConfig] = {s.name: s for s in servers}

    for tool_call in tool_calls:
        tool_call_id = tool_call.get("id", "")
        function_data = tool_call.get("function", {})
        full_name = function_data.get("name", "")
        arguments_str = function_data.get("arguments", "{}")

        # Parse server name and tool name from the prefixed name
        # Format: "{server_name}__{tool_name}"
        if "__" in full_name:
            server_name, tool_name = full_name.split("__", 1)
        else:
            # Fallback: try to find the tool in any server
            tool_name = full_name
            server_name = _find_server_for_tool(tool_name, mcp_tools)
            if not server_name:
                results.append(
                    MCPToolResult(
                        tool_call_id=tool_call_id,
                        server_name="",
                        tool_name=tool_name,
                        result=None,
                        error=f"Could not find MCP server for tool: {tool_name}",
                    )
                )
                continue

        # Get the server configuration
        server = server_map.get(server_name)
        if not server:
            results.append(
                MCPToolResult(
                    tool_call_id=tool_call_id,
                    server_name=server_name,
                    tool_name=tool_name,
                    result=None,
                    error=f"MCP server not found: {server_name}",
                )
            )
            continue

        # Parse arguments
        try:
            arguments = json.loads(arguments_str) if arguments_str else {}
        except json.JSONDecodeError as e:
            results.append(
                MCPToolResult(
                    tool_call_id=tool_call_id,
                    server_name=server_name,
                    tool_name=tool_name,
                    result=None,
                    error=f"Invalid tool arguments JSON: {e}",
                )
            )
            continue

        # Execute the tool
        try:
            result = _execute_tool_on_server(server, tool_name, arguments)
            results.append(
                MCPToolResult(
                    tool_call_id=tool_call_id,
                    server_name=server_name,
                    tool_name=tool_name,
                    result=result,
                )
            )
        except MCPError as e:
            results.append(
                MCPToolResult(
                    tool_call_id=tool_call_id,
                    server_name=server_name,
                    tool_name=tool_name,
                    result=None,
                    error=str(e),
                )
            )

    return results


def _find_server_for_tool(
    tool_name: str, mcp_tools: list[tsi.MCPTool]
) -> str | None:
    """Find the server name for a tool.

    Args:
        tool_name: Name of the tool
        mcp_tools: List of available MCP tools

    Returns:
        Server name if found, None otherwise
    """
    for tool in mcp_tools:
        if tool.name == tool_name:
            return tool.server_name
    return None


def _execute_tool_on_server(
    server: tsi.MCPServerConfig,
    tool_name: str,
    arguments: dict[str, Any],
) -> Any:
    """Execute a tool on an MCP server.

    Args:
        server: The MCP server configuration
        tool_name: Name of the tool to execute
        arguments: Arguments to pass to the tool

    Returns:
        The result from the tool execution
    """
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json, text/event-stream",
        **_get_mcp_headers(server),
    }

    # MCP uses JSON-RPC 2.0 protocol
    request_body = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/call",
        "params": {
            "name": tool_name,
            "arguments": arguments,
        },
    }

    logger.debug(
        f"Executing MCP tool {tool_name} on {server.url} with args: {arguments}"
    )

    try:
        with httpx.Client(timeout=MCP_REQUEST_TIMEOUT) as client:
            response = client.post(
                server.url,
                headers=headers,
                json=request_body,
            )
            response.raise_for_status()
    except httpx.ConnectError as e:
        raise MCPToolExecutionError(f"Could not connect to {server.url}: {e}") from e
    except httpx.TimeoutException as e:
        raise MCPToolExecutionError(f"Timeout connecting to {server.url}: {e}") from e
    except httpx.HTTPStatusError as e:
        raise MCPToolExecutionError(
            f"HTTP error from {server.url}: {e.response.status_code}"
        ) from e

    # Check content type to determine how to parse response
    content_type = response.headers.get("content-type", "")
    response_text = response.text

    logger.debug(
        f"MCP tool execution response from {server.name}: content-type={content_type}, "
        f"length={len(response_text)}, preview={response_text[:500] if response_text else 'empty'}"
    )

    if not response_text or not response_text.strip():
        raise MCPToolExecutionError(f"Empty response from {server.url}")

    # Try to parse response - handle both JSON and SSE formats
    result = None

    # Handle SSE format (text/event-stream)
    if "text/event-stream" in content_type:
        result = _parse_sse_response(response_text)
    else:
        try:
            result = response.json()
        except json.JSONDecodeError:
            # Try SSE parsing as fallback (some servers send SSE with wrong content-type)
            result = _parse_sse_response(response_text)

    if not result:
        raise MCPToolExecutionError(
            f"Could not parse response from {server.url}. "
            f"Content-Type: {content_type}, Response: {response_text[:500]}"
        )

    # Check for JSON-RPC error
    if "error" in result:
        error = result["error"]
        raise MCPToolExecutionError(
            f"MCP error executing {tool_name}: {error.get('message', 'Unknown error')}"
        )

    # Extract content from result
    # MCP tool results have a "content" array with the results
    tool_result = result.get("result", {})
    content = tool_result.get("content", [])

    # If there's only one content item, return it directly
    if len(content) == 1:
        content_item = content[0]
        if content_item.get("type") == "text":
            return content_item.get("text", "")
        return content_item

    # Return the full content array for multiple items
    return content if content else tool_result


def _sanitize_content_for_llm(content: str) -> str:
    """Sanitize content to ensure it's valid for LLM tokenization.

    Removes or replaces characters that could cause tokenization errors.

    Args:
        content: The raw content string

    Returns:
        Sanitized content string safe for LLM APIs
    """
    if not content:
        return content

    # Ensure content is valid UTF-8, replacing invalid sequences
    if isinstance(content, bytes):
        content = content.decode("utf-8", errors="replace")

    # Remove null bytes and other control characters that can cause issues
    # Keep newlines, tabs, and carriage returns
    sanitized = "".join(
        char
        for char in content
        if char in "\n\r\t" or (ord(char) >= 32 and ord(char) != 127)
    )

    return sanitized


def format_tool_results_as_messages(
    tool_results: list[MCPToolResult],
) -> list[dict[str, Any]]:
    """Format MCP tool results as chat messages for the LLM.

    Args:
        tool_results: List of MCPToolResult objects

    Returns:
        List of message dictionaries in OpenAI format
    """
    messages = []

    for result in tool_results:
        if result.error:
            content = f"Error executing tool {result.tool_name}: {result.error}"
        else:
            # Convert result to string if needed
            if isinstance(result.result, str):
                content = result.result
            else:
                content = json.dumps(result.result)

        # Sanitize content to prevent tokenization errors
        content = _sanitize_content_for_llm(content)

        messages.append(
            {
                "role": "tool",
                "tool_call_id": result.tool_call_id,
                "content": content,
            }
        )

    return messages
