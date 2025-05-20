from __future__ import annotations

import importlib
import os
from typing import Any, Callable

from pydantic import AnyUrl

import weave
from weave.integrations.patcher import MultiPatcher, NoOpPatcher, SymbolPatcher
from weave.trace.autopatch import IntegrationSettings, OpSettings

_mcp_client_patcher: MultiPatcher | None = None


def mcp_client_wrapper(settings: OpSettings) -> Callable:
    """Wrapper for MCP client methods."""

    def wrapper(fn: Callable) -> Callable:
        op_kwargs = settings.model_dump()
        op_name = op_kwargs.get("name", "")

        # Special handlings to create synthetic child calls to surface more information
        if op_name.endswith("call_tool"):

            def wrapped_call_tool(*args: Any, **kwargs: Any) -> Any:
                # ClientSession.call_tool(self, name, arguments) is the expected signature
                tool_name = None

                # Try to get tool name from args or kwargs
                if len(args) >= 2:
                    tool_name = args[1]
                elif "name" in kwargs:
                    tool_name = kwargs["name"]

                if tool_name:
                    # Create a new settings object with tool name included in the name and display name
                    base_name = op_name or "mcp.client.session.ClientSession.call_tool"

                    # Set the op name to include the tool name
                    new_op_name = f"{base_name}.{tool_name}"

                    # Use just the tool name as the display name
                    new_settings = settings.model_copy(
                        update={"name": new_op_name, "call_display_name": tool_name}
                    )

                    # Create a new op with the updated settings
                    new_op_kwargs = new_settings.model_dump()
                    op = weave.op(fn, **new_op_kwargs)
                    return op(*args, **kwargs)

                # If we couldn't determine the tool name, just use the original op
                op = weave.op(fn, **op_kwargs)
                return op(*args, **kwargs)

            return wrapped_call_tool
        elif op_name.endswith("read_resource"):

            def wrapped_read_resource(*args: Any, **kwargs: Any) -> Any:
                display_uri = None

                # uri is an object of pydantic `AnyUrl`
                if len(args) >= 2:
                    uri = args[1]
                elif "uri" in kwargs:
                    uri = kwargs["uri"]

                if isinstance(uri, AnyUrl):
                    display_uri = f"{uri.scheme}://{uri.host}"

                if display_uri:
                    base_name = (
                        op_name or "mcp.client.session.ClientSession.read_resource"
                    )
                    new_op_name = f"{base_name}.{display_uri}"
                    new_settings = settings.model_copy(
                        update={"name": new_op_name, "call_display_name": display_uri}
                    )
                    new_op_kwargs = new_settings.model_dump()
                    op = weave.op(fn, **new_op_kwargs)
                    return op(*args, **kwargs)

                op = weave.op(fn, **op_kwargs)
                return op(*args, **kwargs)

            return wrapped_read_resource
        elif op_name.endswith("get_prompt"):

            def wrapped_get_prompt(*args: Any, **kwargs: Any) -> Any:
                prompt_name = None

                if len(args) >= 2:
                    prompt_name = args[1]
                elif "name" in kwargs:
                    prompt_name = kwargs["name"]

                if prompt_name:
                    base_name = op_name or "mcp.client.session.ClientSession.get_prompt"
                    new_op_name = f"{base_name}.{prompt_name}"
                    new_settings = settings.model_copy(
                        update={"name": new_op_name, "call_display_name": prompt_name}
                    )
                    new_op_kwargs = new_settings.model_dump()
                    op = weave.op(fn, **new_op_kwargs)
                    return op(*args, **kwargs)

                op = weave.op(fn, **op_kwargs)
                return op(*args, **kwargs)

            return wrapped_get_prompt
        else:
            # For other methods, use the standard wrapper
            op = weave.op(fn, **op_kwargs)
            return op

    return wrapper


def get_mcp_client_patcher(
    settings: IntegrationSettings | None = None,
) -> MultiPatcher | NoOpPatcher:
    if settings is None:
        settings = IntegrationSettings()

    if not settings.enabled:
        return NoOpPatcher()

    global _mcp_client_patcher
    if _mcp_client_patcher is not None:
        return _mcp_client_patcher

    base = settings.op_settings

    # Settings for core client methods
    call_tool_settings = base.model_copy(
        update={
            "name": base.name or "mcp.client.session.ClientSession.call_tool",
            "call_display_name": base.call_display_name or "ClientSession.call_tool",
        }
    )

    list_tools_settings = base.model_copy(
        update={
            "name": base.name or "mcp.client.session.ClientSession.list_tools",
            "call_display_name": base.call_display_name or "ClientSession.list_tools",
        }
    )

    read_resource_settings = base.model_copy(
        update={
            "name": base.name or "mcp.client.session.ClientSession.read_resource",
            "call_display_name": base.call_display_name
            or "ClientSession.read_resource",
        }
    )

    list_resources_settings = base.model_copy(
        update={
            "name": base.name or "mcp.client.session.ClientSession.list_resources",
            "call_display_name": base.call_display_name
            or "ClientSession.list_resources",
        }
    )

    list_prompts_settings = base.model_copy(
        update={
            "name": base.name or "mcp.client.session.ClientSession.list_prompts",
            "call_display_name": base.call_display_name or "ClientSession.list_prompts",
        }
    )

    get_prompt_settings = base.model_copy(
        update={
            "name": base.name or "mcp.client.session.ClientSession.get_prompt",
            "call_display_name": base.call_display_name or "ClientSession.get_prompt",
        }
    )

    # Create patchers for all methods we want to trace
    patchers = [
        # Core client methods
        SymbolPatcher(
            lambda: importlib.import_module("mcp.client.session"),
            "ClientSession.call_tool",
            mcp_client_wrapper(call_tool_settings),
        ),
        SymbolPatcher(
            lambda: importlib.import_module("mcp.client.session"),
            "ClientSession.read_resource",
            mcp_client_wrapper(read_resource_settings),
        ),
        SymbolPatcher(
            lambda: importlib.import_module("mcp.client.session"),
            "ClientSession.get_prompt",
            mcp_client_wrapper(get_prompt_settings),
        ),
    ]

    trace_list_operations = os.environ.get("MCP_TRACE_LIST_OPERATIONS", "").lower() in (
        "true",
        "1",
        "yes",
    )
    if trace_list_operations:
        patchers.extend(
            [
                SymbolPatcher(
                    lambda: importlib.import_module("mcp.client.session"),
                    "ClientSession.list_tools",
                    mcp_client_wrapper(list_tools_settings),
                ),
                SymbolPatcher(
                    lambda: importlib.import_module("mcp.client.session"),
                    "ClientSession.list_resources",
                    mcp_client_wrapper(list_resources_settings),
                ),
                SymbolPatcher(
                    lambda: importlib.import_module("mcp.client.session"),
                    "ClientSession.list_prompts",
                    mcp_client_wrapper(list_prompts_settings),
                ),
            ]
        )

    _mcp_client_patcher = MultiPatcher(patchers)

    return _mcp_client_patcher
