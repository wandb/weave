"""Core runtime components for the Claude Code plugin.

This module provides lazy imports to avoid circular dependencies.
Import directly from submodules when needed:
    from weave.integrations.claude_plugin.core.daemon import WeaveDaemon
    from weave.integrations.claude_plugin.core.hook import main as hook_main
    from weave.integrations.claude_plugin.core.socket_client import DaemonClient
    from weave.integrations.claude_plugin.core.state import StateManager
"""
