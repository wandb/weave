from __future__ import annotations

import importlib
import os
from typing import Any, Callable

import weave
from weave.integrations.patcher import MultiPatcher, NoOpPatcher, SymbolPatcher
from weave.trace.autopatch import IntegrationSettings, OpSettings

_mcp_server_patcher: MultiPatcher | None = None


def mcp_server_wrapper(settings: OpSettings) -> Callable:
    """Wrapper for MCP server methods."""

    def wrapper(fn: Callable) -> Callable:
        op_kwargs = settings.model_dump()
        op = weave.op(fn, **op_kwargs)
        return op

    return wrapper


def decorator_wrapper(settings: OpSettings) -> Callable:
    """Wrapper for MCP server decorators like tool, resource, prompt."""

    def outer_wrapper(decorator_fn: Callable) -> Callable:
        def wrapped_decorator(*args: Any, **kwargs: Any) -> Callable:
            # Store the original decorator
            original_decorator = decorator_fn(*args, **kwargs)

            # Create a new decorator that wraps the function with weave.op
            def new_decorator(fn: Callable) -> Callable:
                weave_op_name = fn.__name__ or ""
                base_name = settings.name or ""

                # Set the op name to mcp.server.fastmcp.FastMCP.tool.<TOOL_NAME>
                op_name = (
                    f"{base_name}.{weave_op_name}" if weave_op_name != "" else base_name
                )

                # Use just the function name as the display name
                display_name = weave_op_name if weave_op_name != "" else base_name

                settings_copy = settings.model_copy(
                    update={"name": op_name, "call_display_name": display_name}
                )

                weave_wrapped = weave.op(fn, **settings_copy.model_dump())

                # Then apply the original decorator
                return original_decorator(weave_wrapped)

            return new_decorator

        return wrapped_decorator

    return outer_wrapper


def get_mcp_server_patcher(
    settings: IntegrationSettings | None = None,
) -> MultiPatcher | NoOpPatcher:
    if settings is None:
        settings = IntegrationSettings()

    if not settings.enabled:
        return NoOpPatcher()

    global _mcp_server_patcher
    if _mcp_server_patcher is not None:
        return _mcp_server_patcher

    base = settings.op_settings

    # Settings for core methods
    call_tool_settings = base.model_copy(
        update={
            "name": base.name or "mcp.server.fastmcp.FastMCP.call_tool",
            "call_display_name": base.call_display_name or "FastMCP.call_tool",
        }
    )

    list_tools_settings = base.model_copy(
        update={
            "name": base.name or "mcp.server.fastmcp.FastMCP.list_tools",
            "call_display_name": base.call_display_name or "FastMCP.list_tools",
        }
    )

    read_resource_settings = base.model_copy(
        update={
            "name": base.name or "mcp.server.fastmcp.FastMCP.read_resource",
            "call_display_name": base.call_display_name or "FastMCP.read_resource",
        }
    )

    list_resources_settings = base.model_copy(
        update={
            "name": base.name or "mcp.server.fastmcp.FastMCP.list_resources",
            "call_display_name": base.call_display_name or "FastMCP.list_resources",
        }
    )

    # Settings for decorator methods
    tool_decorator_settings = base.model_copy(
        update={
            "name": base.name or "mcp.server.fastmcp.FastMCP.tool",
            "call_display_name": base.call_display_name or "FastMCP.tool",
        }
    )

    resource_decorator_settings = base.model_copy(
        update={
            "name": base.name or "mcp.server.fastmcp.FastMCP.resource",
            "call_display_name": base.call_display_name or "FastMCP.resource",
        }
    )

    prompt_decorator_settings = base.model_copy(
        update={
            "name": base.name or "mcp.server.fastmcp.FastMCP.prompt",
            "call_display_name": base.call_display_name or "FastMCP.prompt",
        }
    )

    # Create patchers for all methods we want to trace
    patchers = [
        # Core methods
        SymbolPatcher(
            lambda: importlib.import_module("mcp.server.fastmcp"),
            "FastMCP.call_tool",
            mcp_server_wrapper(call_tool_settings),
        ),
        SymbolPatcher(
            lambda: importlib.import_module("mcp.server.fastmcp"),
            "FastMCP.read_resource",
            mcp_server_wrapper(read_resource_settings),
        ),
        # Decorator methods
        SymbolPatcher(
            lambda: importlib.import_module("mcp.server.fastmcp"),
            "FastMCP.tool",
            decorator_wrapper(tool_decorator_settings),
        ),
        SymbolPatcher(
            lambda: importlib.import_module("mcp.server.fastmcp"),
            "FastMCP.resource",
            decorator_wrapper(resource_decorator_settings),
        ),
        SymbolPatcher(
            lambda: importlib.import_module("mcp.server.fastmcp"),
            "FastMCP.prompt",
            decorator_wrapper(prompt_decorator_settings),
        ),
    ]

    # Only add list_* operations if opted in via environment variable
    trace_list_operations = os.environ.get("MCP_TRACE_LIST_OPERATIONS", "").lower() in (
        "true",
        "1",
        "yes",
    )
    if trace_list_operations:
        patchers.extend(
            [
                SymbolPatcher(
                    lambda: importlib.import_module("mcp.server.fastmcp"),
                    "FastMCP.list_tools",
                    mcp_server_wrapper(list_tools_settings),
                ),
                SymbolPatcher(
                    lambda: importlib.import_module("mcp.server.fastmcp"),
                    "FastMCP.list_resources",
                    mcp_server_wrapper(list_resources_settings),
                ),
            ]
        )

    _mcp_server_patcher = MultiPatcher(patchers)

    return _mcp_server_patcher
