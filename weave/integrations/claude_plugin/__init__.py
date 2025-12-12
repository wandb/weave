"""Claude Code Plugin integration for Weave.

This package provides real-time Weave tracing for Claude Code sessions
via the Claude Code hooks system. It also contains shared code used by
the batch import script (scripts/import_claude_sessions.py).

Components:
- session_parser: Parse Claude Code session JSONL files
- state: Persist hook state across process invocations
- handlers: Hook event handlers for real-time tracing
- credentials: Claude Code OAuth credential management
- session_title: Session title generation using Claude API
- utils: Shared utilities
- hook: Entry point for hook invocations

Usage:
    # Enable real-time tracing via Claude Code hooks:
    # Set WEAVE_PROJECT="entity/project" and configure hooks to run:
    # python -m weave.integrations.claude_plugin

    # Import shared utilities in your code:
    from weave.integrations.claude_plugin import (
        Session,
        parse_session_file,
        generate_session_name,
        get_oauth_credentials,
        generate_session_title,
    )
"""

from weave.integrations.claude_plugin.credentials import (
    OAUTH_BETA_HEADER,
    OAuthCredentials,
    get_api_headers,
    get_oauth_credentials,
)
from weave.integrations.claude_plugin.session_parser import (
    AssistantMessage,
    FileBackup,
    Session,
    TokenUsage,
    ToolCall,
    Turn,
    UserMessage,
    is_system_message,
    parse_session_file,
    parse_timestamp,
)
from weave.integrations.claude_plugin.session_title import (
    analyze_session_title,
    generate_session_title,
)
from weave.integrations.claude_plugin.state import (
    StateManager,
    create_session_data,
    delete_session,
    load_session,
    save_session,
)
from weave.integrations.claude_plugin.utils import (
    generate_session_name,
    get_tool_display_name,
    truncate,
)

__all__ = [
    # Session parser
    "Session",
    "Turn",
    "TokenUsage",
    "ToolCall",
    "FileBackup",
    "AssistantMessage",
    "UserMessage",
    "parse_session_file",
    "parse_timestamp",
    "is_system_message",
    # State
    "StateManager",
    "create_session_data",
    "load_session",
    "save_session",
    "delete_session",
    # Credentials
    "OAuthCredentials",
    "get_oauth_credentials",
    "get_api_headers",
    "OAUTH_BETA_HEADER",
    # Session title
    "analyze_session_title",
    "generate_session_title",
    # Utils
    "truncate",
    "get_tool_display_name",
    "generate_session_name",
]
