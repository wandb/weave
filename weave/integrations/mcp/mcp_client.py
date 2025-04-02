print("I AM IN THE MCP CLIENT INTEGRATION")
import importlib
from typing import Callable

import weave
from weave.integrations.patcher import MultiPatcher, NoOpPatcher, SymbolPatcher
from weave.trace.autopatch import IntegrationSettings, OpSettings

_mcp_client_patcher: MultiPatcher | None = None


def mcp_client_wrapper(settings: OpSettings) -> Callable:
    """Wrapper for MCP client methods."""

    def wrapper(fn: Callable) -> Callable:
        op_kwargs = settings.model_dump()
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

    # initialize_settings = base.model_copy(
    #     update={
    #         "name": base.name or "mcp.client.session.ClientSession.initialize",
    #         "call_display_name": base.call_display_name or "ClientSession.initialize",
    #     }
    # )

    print("Creating patchers for MCP client methods")
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
            "ClientSession.list_tools",
            mcp_client_wrapper(list_tools_settings),
        ),
        SymbolPatcher(
            lambda: importlib.import_module("mcp.client.session"),
            "ClientSession.read_resource",
            mcp_client_wrapper(read_resource_settings),
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
        SymbolPatcher(
            lambda: importlib.import_module("mcp.client.session"),
            "ClientSession.get_prompt",
            mcp_client_wrapper(get_prompt_settings),
        ),
        # SymbolPatcher(
        #     lambda: importlib.import_module("mcp.client.session"),
        #     "ClientSession.initialize",
        #     mcp_client_wrapper(initialize_settings),
        # ),
    ]
    print("client patchers", patchers)

    _mcp_client_patcher = MultiPatcher(patchers)

    return _mcp_client_patcher
