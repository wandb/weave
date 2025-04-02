print("I AM IN THE INTEGRATION")
from typing import Callable, Any, Dict
import importlib
import weave

from weave.integrations.patcher import Patcher
from weave.integrations.patcher import MultiPatcher, NoOpPatcher, SymbolPatcher
from weave.trace.autopatch import IntegrationSettings, OpSettings
from weave.trace.serialization.serialize import dictify

_mcp_server_patcher: MultiPatcher | None = None


def mcp_server_wrapper(settings: OpSettings) -> Callable:
    """Wrapper for MCP server methods."""
    def wrapper(fn: Callable) -> Callable:
        op_kwargs = settings.model_dump()
        op = weave.op(fn, **op_kwargs)
        return op

    return wrapper


def get_mcp_server_patcher(
        settings: IntegrationSettings | None = None
    ) -> MultiPatcher | NoOpPatcher:
    if settings is None:
        settings = IntegrationSettings()

    if not settings.enabled:
        return NoOpPatcher()

    global _mcp_server_patcher
    if _mcp_server_patcher is not None:
        return _mcp_server_patcher

    base = settings.op_settings
    print("base", base)

    call_tool_settings = base.model_copy(
        update={
            "name": base.name or "mcp.server.fastmcp.FastMCP.call_tool",
            "call_display_name": base.call_display_name or "FastMCP.call_tool",
        }
    )
    print("call_tool_settings", call_tool_settings)
    
    # Create patchers for all methods we want to trace
    patchers = [
        SymbolPatcher(
            lambda: importlib.import_module("mcp.server.fastmcp"),
            "mcp.server.fastmcp.FastMCP.call_tool",
            mcp_server_wrapper(call_tool_settings),
        ),
    ]
    print("patchers", patchers)

    _mcp_server_patcher = MultiPatcher(patchers)

    return _mcp_server_patcher
