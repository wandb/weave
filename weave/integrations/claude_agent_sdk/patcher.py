"""Lifecycle patchers for the Claude Agent SDK integration.

Two patcher variants share the SDK install surface:

- ``ClaudeAgentSdkPatcher`` (calls-based) — installs the legacy
  Weave-calls behaviour exposed by
  ``claude_agent_sdk.claude_agent_sdk_integration``.
- ``ClaudeAgentSdkOtelPatcher`` (OTel-based) — wraps the public surface
  in ``otel_processor`` to emit ``gen_ai`` semconv spans for the Agents
  tab.

The two variants are intentionally near-identical — only the wrapper
factories they install differ. The dispatcher in
``weave/integrations/patch.py`` picks which one runs based on
``WEAVE_USE_OTEL_V2``.
"""

from __future__ import annotations

import importlib

from weave.integrations.patcher import MultiPatcher, NoOpPatcher, SymbolPatcher
from weave.trace.autopatch import IntegrationSettings

_claude_agent_sdk_patcher: MultiPatcher | None = None
_claude_agent_sdk_otel_patcher: MultiPatcher | None = None


def get_claude_agent_sdk_patcher(
    settings: IntegrationSettings | None = None,
) -> MultiPatcher | NoOpPatcher:
    """Calls-based variant — Weave child calls under a root agent call."""
    from weave.integrations.claude_agent_sdk.claude_agent_sdk_integration import (
        _patched_init_wrapper,
        _patched_process_query_wrapper,
    )

    if settings is None:
        settings = IntegrationSettings()

    if not settings.enabled:
        return NoOpPatcher()

    global _claude_agent_sdk_patcher  # noqa: PLW0603
    if _claude_agent_sdk_patcher is not None:
        return _claude_agent_sdk_patcher

    _claude_agent_sdk_patcher = MultiPatcher(
        [
            SymbolPatcher(
                lambda: importlib.import_module("claude_agent_sdk._internal.client"),
                "InternalClient.process_query",
                _patched_process_query_wrapper(settings),
            ),
            SymbolPatcher(
                lambda: importlib.import_module("claude_agent_sdk"),
                "ClaudeSDKClient.__init__",
                _patched_init_wrapper(settings),
            ),
        ]
    )

    return _claude_agent_sdk_patcher


def get_claude_agent_sdk_otel_patcher(
    settings: IntegrationSettings | None = None,
) -> MultiPatcher | NoOpPatcher:
    """OTel variant — emits ``gen_ai`` semconv spans for the Agents tab.

    Wraps the public SDK surface (``query()`` and three ``ClaudeSDKClient``
    methods). Each ``query()`` / ``receive_response()`` becomes an
    ``invoke_agent`` root span; tools execute under ``execute_tool``
    children driven by SDK ``PreToolUse`` / ``PostToolUse`` hooks; and
    subagents nest as ``invoke_agent`` spans under the tool that spawned
    them.
    """
    from weave.integrations.claude_agent_sdk.otel_processor import (
        make_client_connect_wrapper,
        make_client_query_wrapper,
        make_client_receive_response_wrapper,
        make_process_query_wrapper,
    )

    if settings is None:
        settings = IntegrationSettings()

    if not settings.enabled:
        return NoOpPatcher()

    global _claude_agent_sdk_otel_patcher  # noqa: PLW0603
    if _claude_agent_sdk_otel_patcher is not None:
        return _claude_agent_sdk_otel_patcher

    _claude_agent_sdk_otel_patcher = MultiPatcher(
        [
            # Patch the shared internal entry point both ``query()`` and
            # ``ClaudeSDKClient.receive_response()`` delegate to. As a
            # class method, this patch survives Python's import-order
            # semantics — patching the module-level ``query`` attribute
            # is too late if the user already did
            # ``from claude_agent_sdk import query`` before ``weave.init``.
            SymbolPatcher(
                lambda: importlib.import_module("claude_agent_sdk._internal.client"),
                "InternalClient.process_query",
                make_process_query_wrapper(settings),
            ),
            SymbolPatcher(
                lambda: importlib.import_module("claude_agent_sdk.client"),
                "ClaudeSDKClient.connect",
                make_client_connect_wrapper(settings),
            ),
            SymbolPatcher(
                lambda: importlib.import_module("claude_agent_sdk.client"),
                "ClaudeSDKClient.query",
                make_client_query_wrapper(settings),
            ),
            SymbolPatcher(
                lambda: importlib.import_module("claude_agent_sdk.client"),
                "ClaudeSDKClient.receive_response",
                make_client_receive_response_wrapper(settings),
            ),
        ]
    )

    return _claude_agent_sdk_otel_patcher
