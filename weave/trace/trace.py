from __future__ import annotations

import dataclasses
import datetime
from collections import defaultdict
from collections.abc import Iterator

from weave.trace.call import Call
from weave.trace.vals import WeaveObject


@dataclasses.dataclass
class Trace:
    """A complete trace tree loaded in a single round-trip.

    Instead of calling ``call.children()`` recursively (N+1 queries), use
    ``client.get_trace(trace_id)`` to fetch every call in the trace at once
    and navigate the tree client-side.

    Example::

        trace = client.get_trace("abc-123")
        print(trace.root.func_name, trace.duration)

        for depth, call in trace.walk():
            print("  " * depth + call.func_name)

        llm_calls = trace.find("openai.chat.completions.create")
    """

    trace_id: str
    root: Call
    _calls: list[Call]
    _children_by_parent: dict[str | None, list[Call]]

    # ── traversal ──────────────────────────────────────────────

    def children_of(self, call: Call) -> list[Call]:
        """Direct children of *call*, already loaded — no server hit."""
        return self._children_by_parent.get(call.id, [])

    def walk(self, *, from_call: Call | None = None) -> Iterator[tuple[int, Call]]:
        """DFS yielding ``(depth, call)`` pairs.

        Args:
            from_call: Start the walk from this call instead of the root.
        """
        start = from_call or self.root
        stack: list[tuple[int, Call]] = [(0, start)]
        while stack:
            depth, current = stack.pop()
            yield depth, current
            # Push children in reverse so the first child is visited first.
            for child in reversed(self.children_of(current)):
                stack.append((depth + 1, child))

    def find(self, op_name: str) -> list[Call]:
        """Return all calls whose ``func_name`` contains *op_name*."""
        return [c for c in self._calls if op_name in c.func_name]

    # ── properties ─────────────────────────────────────────────

    @property
    def calls(self) -> list[Call]:
        """All calls in the trace, ordered by start time."""
        return list(self._calls)

    @property
    def depth(self) -> int:
        """Maximum nesting depth of the trace."""
        return max(d for d, _ in self.walk()) if self._calls else 0

    @property
    def duration(self) -> datetime.timedelta | None:
        """Wall-clock duration from root start to the latest call end."""
        if not self.root.started_at:
            return None
        ends = [c.ended_at for c in self._calls if c.ended_at is not None]
        if not ends:
            return None
        return max(ends) - self.root.started_at

    @property
    def call_count(self) -> int:
        return len(self._calls)

    def __repr__(self) -> str:
        return (
            f"Trace(trace_id={self.trace_id!r}, "
            f"root={self.root.func_name!r}, "
            f"calls={self.call_count})"
        )


def build_trace(trace_id: str, calls: list[WeaveObject]) -> Trace:
    """Assemble a ``Trace`` from a flat list of calls.

    The calls must all share the same ``trace_id``.  They are sorted by
    ``started_at`` and organised into a parent→children index.
    """
    if not calls:
        raise ValueError(f"No calls found for trace_id={trace_id!r}")

    # Unwrap WeaveObject → Call
    raw_calls: list[Call] = [_unwrap_call(c) for c in calls]
    raw_calls.sort(key=lambda c: c.started_at or datetime.datetime.min)

    children_by_parent: dict[str | None, list[Call]] = defaultdict(list)
    calls_by_id: dict[str, Call] = {}

    for call in raw_calls:
        calls_by_id[call.id] = call  # type: ignore[assignment]
        children_by_parent[call.parent_id].append(call)

    # Root is the call whose parent_id is None or whose parent is not in this trace.
    roots = [
        c
        for c in raw_calls
        if c.parent_id is None or c.parent_id not in calls_by_id
    ]
    if not roots:
        raise ValueError(f"Could not find root call for trace_id={trace_id!r}")

    root = roots[0]

    return Trace(
        trace_id=trace_id,
        root=root,
        _calls=raw_calls,
        _children_by_parent=dict(children_by_parent),
    )


def _unwrap_call(obj: WeaveObject) -> Call:
    """Extract the underlying ``Call`` from a ``WeaveObject`` wrapper."""
    inner = obj._val if hasattr(obj, "_val") else obj
    if not isinstance(inner, Call):
        raise TypeError(f"Expected Call, got {type(inner)}")
    return inner
