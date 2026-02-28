"""Base types for tool configuration.

Tool configurations describe special behaviors that tools exhibit,
which the trace builder uses to create appropriate traces and views.
"""

from typing import TypedDict


class ToolConfig(TypedDict, total=False):
    """Configuration for a tool's special behaviors.

    All fields are optional - only specify what applies to the tool.
    """

    # Subagent spawning
    spawns_subagent: bool  # Tool spawns a nested agent run
    subagent_id_field: str  # Path to agent ID in metadata (e.g., "metadata.agentId")

    # Views
    has_diff_view: bool  # Tool results should show file diffs
    has_custom_view: bool  # Tool has a custom HTML view

    # Flow control
    is_qa_flow: bool  # Tool initiates a Q&A flow with user

    # Metadata extraction
    metadata_fields: list[str]  # Fields to extract to event metadata
