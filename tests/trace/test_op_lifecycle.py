"""Unit tests for the shared op call lifecycle (``weave.trace.op_lifecycle``).

Before the lifecycle was extracted, the "finish this call exactly once" logic
lived as a closure duplicated across the four ``op.py`` execution paths and
could only be exercised by driving a full op execution. ``CallFinisher`` makes
that behavior directly constructable, so these tests assert its contract
(finish-once idempotency, the ``require_explicit_finish`` opt-out, and finish
post-processing) through the real client at the ``finish_call`` seam.
"""

from __future__ import annotations

import weave
from weave.trace.op_lifecycle import CallFinisher


def test_call_finisher_finishes_call_once(client) -> None:
    @weave.op
    def add(a: int, b: int) -> int:
        return a + b

    call = client.create_call(add, {"a": 1, "b": 2})
    finisher = CallFinisher(add, call, client)

    finisher(output=3)

    assert finisher.has_finished is True
    assert call.ended_at is not None
    ended_at_first = call.ended_at

    # A second invocation is a no-op: the call must not be finished twice.
    finisher(output=999)
    assert call.ended_at == ended_at_first


def test_call_finisher_respects_require_explicit_finish(client) -> None:
    @weave.op
    def add(a: int, b: int) -> int:
        return a + b

    call = client.create_call(add, {"a": 1, "b": 2})
    finisher = CallFinisher(add, call, client, require_explicit_finish=True)

    # With require_explicit_finish, calling the finisher does nothing; the
    # caller (e.g. the imperative eval logger) finishes the call itself.
    finisher(output=3)
    assert finisher.has_finished is False
    assert call.ended_at is None

    # Clean up so the call doesn't dangle on the context stack.
    client.finish_call(call, 3)


def test_call_finisher_applies_finish_post_processor(client) -> None:
    @weave.op
    def add(a: int, b: int) -> int:
        return a + b

    # _on_finish_post_processor is the hook integrations install (e.g. via
    # _add_accumulator) to transform the final output before it is logged.
    add._on_finish_post_processor = lambda output: {"wrapped": output}

    call = client.create_call(add, {"a": 1, "b": 2})
    finisher = CallFinisher(add, call, client)

    finisher(output=3)
    assert call.output == {"wrapped": 3}


def test_call_finisher_records_exception(client) -> None:
    @weave.op
    def add(a: int, b: int) -> int:
        return a + b

    call = client.create_call(add, {"a": 1, "b": 2})
    finisher = CallFinisher(add, call, client)

    err = ValueError("boom")
    finisher(exception=err)

    assert finisher.has_finished is True
    assert call.ended_at is not None
    assert call.exception is not None
