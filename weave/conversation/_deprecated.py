"""Deprecated ``session``-named aliases for the Conversation SDK.

The SDK was renamed from "Session" to "Conversation". These thin wrappers
keep the old public names working and emit a ``DeprecationWarning``; they
translate the old ``session_id`` / ``session_name`` keyword arguments to
``conversation_id`` / ``conversation_name``. Quarantined here so the renamed
core stays free of legacy naming. Remove in a future release.
"""

from __future__ import annotations

import warnings
from typing import TYPE_CHECKING, Any

from weave.conversation.conversation import (
    Conversation,
    LogResult,
    Turn,
    end_conversation,
    get_current_conversation,
    log_conversation,
    start_conversation,
)

if TYPE_CHECKING:
    from opentelemetry.util.types import Attributes

__all__ = [
    "Session",
    "end_session",
    "get_current_session",
    "log_session",
    "start_session",
]


def _warn(old: str, new: str) -> None:
    """Emit the rename ``DeprecationWarning`` for ``weave.<old>``.

    ``stacklevel=3`` points the warning at the user's call site (caller →
    public alias → ``_warn``) rather than at this module.
    """
    warnings.warn(
        f"weave.{old} is deprecated and will be removed in a future release; "
        f"use weave.{new} instead.",
        DeprecationWarning,
        stacklevel=3,
    )


def start_session(
    *,
    agent_name: str = "",
    model: str = "",
    session_id: str = "",
    session_name: str = "",
    include_content: bool = True,
    continue_parent_trace: bool = False,
    attributes: Attributes = None,
) -> Conversation:
    """Deprecated alias of :func:`weave.start_conversation`.

    ``session_id`` / ``session_name`` map to ``conversation_id`` /
    ``conversation_name``.
    """
    _warn("start_session", "start_conversation")
    return start_conversation(
        agent_name=agent_name,
        model=model,
        conversation_id=session_id,
        conversation_name=session_name,
        include_content=include_content,
        continue_parent_trace=continue_parent_trace,
        attributes=attributes,
    )


def log_session(
    *,
    turns: list[Turn],
    session_id: str = "",
    session_name: str = "",
    agent_name: str = "",
    model: str = "",
    include_content: bool = True,
    continue_parent_trace: bool = False,
    attributes: Attributes = None,
) -> LogResult:
    """Deprecated alias of :func:`weave.log_conversation`.

    ``session_id`` / ``session_name`` map to ``conversation_id`` /
    ``conversation_name``.
    """
    _warn("log_session", "log_conversation")
    return log_conversation(
        turns=turns,
        conversation_id=session_id,
        conversation_name=session_name,
        agent_name=agent_name,
        model=model,
        include_content=include_content,
        continue_parent_trace=continue_parent_trace,
        attributes=attributes,
    )


def end_session() -> None:
    """Deprecated alias of :func:`weave.end_conversation`."""
    _warn("end_session", "end_conversation")
    end_conversation()


def get_current_session() -> Conversation | None:
    """Deprecated alias of :func:`weave.get_current_conversation`."""
    _warn("get_current_session", "get_current_conversation")
    return get_current_conversation()


class Session(Conversation):
    """Deprecated alias of :class:`weave.Conversation`.

    Accepts the old ``session_id`` / ``session_name`` constructor fields and
    also exposes them as read/write properties that proxy to
    ``conversation_id`` / ``conversation_name``. The original ``Session`` had
    these as model fields, so old code that reads or assigns ``s.session_id``
    keeps working.
    """

    def __init__(self, **data: Any) -> None:
        _warn("Session", "Conversation")
        if "session_id" in data:
            data.setdefault("conversation_id", data.pop("session_id"))
        if "session_name" in data:
            data.setdefault("conversation_name", data.pop("session_name"))
        super().__init__(**data)

    @property
    def session_id(self) -> str:
        """Deprecated alias of :attr:`conversation_id`."""
        return self.conversation_id

    @session_id.setter
    def session_id(self, value: str) -> None:
        self.conversation_id = value

    @property
    def session_name(self) -> str:
        """Deprecated alias of :attr:`conversation_name`."""
        return self.conversation_name

    @session_name.setter
    def session_name(self, value: str) -> None:
        self.conversation_name = value
