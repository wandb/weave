"""Read values out of arbitrary call payloads, and infer which paths a project uses.

Weave ops have no fixed signature, so every field this needs is addressed by a path that is either
configured or inferred from a sample of the project's own root calls.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence

Row = dict[str, object]


def resolve(payload: object, path: str) -> object:
    """Read a dotted path, where a trailing `[i]` on a step indexes into a list."""
    current = payload
    for step in path.split("."):
        key, _, raw_index = step.partition("[")
        if not isinstance(current, Mapping):
            return None
        current = current.get(key)
        if not raw_index:
            continue
        index = int(raw_index.rstrip("]"))
        if not isinstance(current, Sequence) or isinstance(current, str):
            return None
        if not -len(current) <= index < len(current):
            return None
        current = current[index]
    return current


def text_of(value: object) -> str:
    """Flatten a payload fragment to text, including the content-parts list shape."""
    if isinstance(value, str):
        return value
    if isinstance(value, Mapping):
        for key in CONTENT_KEYS:
            text = text_of(value.get(key))
            if text:
                return text
        return ""
    if isinstance(value, Sequence):
        return "\n".join(part for part in (text_of(item) for item in value) if part)
    return ""


def resolve_text(payload: Row, paths: Sequence[str]) -> str:
    """The first path that yields text, so one mapping covers slightly different ops."""
    for path in paths:
        text = text_of(resolve(payload, path))
        if text:
            return text
    return ""


def last_user_message_text(payload: Row) -> str:
    """The last role=user item in `inputs.messages`, which is the turn text once the list is a history."""
    messages = resolve(payload, "inputs.messages")
    if not isinstance(messages, Sequence) or isinstance(messages, str):
        return ""
    for item in reversed(messages):
        if isinstance(item, Mapping) and str(item.get("role") or "") == "user":
            return text_of(item.get("content"))
    return ""


def detect_paths(rows: Sequence[Row], paths: Iterable[str]) -> list[str]:
    """Every candidate some sampled root carries, in candidate order."""
    return [path for path in paths if any(text_of(resolve(row, path)) for row in rows)]


def infer_mapping(sample: list[Row], overrides: dict[str, str]) -> dict[str, list[str]]:
    """The paths this project actually uses, keeping every one a root call was seen to carry.

    One project can expose several entry points with different signatures, so each role keeps a
    candidate list and a call takes the first path that yields text for that call.
    """
    candidates = {
        "conversation": CONVERSATION_PATHS,
        "user": USER_TEXT_PATHS,
        "assistant": ASSISTANT_TEXT_PATHS,
    }
    mapping = {
        role: [overrides[role]] if overrides.get(role) else detect_paths(sample, paths)
        for role, paths in candidates.items()
    }
    if not mapping["user"] and any(last_user_message_text(row) for row in sample):
        mapping["user"] = ["inputs.messages"]
    for role in ("user", "assistant"):
        if not mapping[role]:
            keys = sorted({key for row in sample for key in _payload_keys(row)})
            raise SystemExit(
                f"could not find the {role} text; pass --{role}-path. Keys seen: {keys[:20]}"
            )
    return mapping


def select_columns(paths: Iterable[str]) -> list[str]:
    """The narrowest column set that still returns every path, given two server behaviours.

    Asking for a field *and* its sub-fields silently returns only the sub-fields, and sub-selecting
    a field whose value is a scalar replaces that scalar with an object of nulls. So a field needed
    whole wins, and its sub-columns are dropped.
    """
    columns = {path.split("[")[0] for path in paths}
    whole = {column for column in columns if "." not in column}
    return sorted(whole | {c for c in columns if c.split(".")[0] not in whole})


def _payload_keys(row: Row) -> list[str]:
    keys = []
    for field in ("inputs", "output", "attributes"):
        value = row.get(field)
        if isinstance(value, Mapping):
            keys.extend(f"{field}.{key}" for key in value)
    return keys


CONTENT_KEYS = ("content", "text", "message", "output", "answer", "response")

CONVERSATION_PATHS = (
    "attributes.sessionId",
    "attributes.session_id",
    "attributes.conversationId",
    "attributes.conversation_id",
    "attributes.threadId",
    "attributes.thread_id",
    "inputs.session_id",
    "inputs.sessionId",
    "inputs.conversation_id",
    "inputs.thread_id",
)

USER_TEXT_PATHS = (
    "inputs.message",
    "inputs.query",
    "inputs.prompt",
    "inputs.question",
    "inputs.task",
    "inputs.goal",
    "inputs.user_input",
    "inputs.user_message",
    "inputs.input",
    "inputs.text",
)

ASSISTANT_TEXT_PATHS = (
    "output.content",
    "output.choices[0].message.content",
    "output.messages[-1].content",
    "output.output",
    "output.response",
    "output.answer",
    "output.text",
    "output",
)
