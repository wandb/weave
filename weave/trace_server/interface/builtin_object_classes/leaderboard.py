"""Compatibility imports; definitions live in weave.shared.trace_server."""

from weave.shared.trace_server.interface.builtin_object_classes.leaderboard import (
    BaseModel,
    Leaderboard,
    LeaderboardColumn,
    base_object_def,
)

__all__ = ["BaseModel", "Leaderboard", "LeaderboardColumn", "base_object_def"]
