from __future__ import annotations

import weave
from weave.trace_server import trace_server_interface as tsi


def test_move_calls_basic(client):
    """Move completed calls from one project to another."""

    @weave.op
    def my_op(x: int) -> int:
        return x + 1

    my_op(1)
    my_op(2)

    source_project = client._project_id()
    dest_project = source_project + "-dest"

    # Verify calls exist in source
    src_calls = client.server.calls_query(
        tsi.CallsQueryReq(project_id=source_project)
    ).calls
    assert len(src_calls) == 2
    original_ids = {c.id for c in src_calls}

    # Move calls
    moved = client.move_calls(
        call_ids=list(original_ids),
        to_project=dest_project,
    )
    assert moved == 2

    # Source should have no calls (moved away)
    src_after = client.server.calls_query(
        tsi.CallsQueryReq(project_id=source_project)
    ).calls
    assert len(src_after) == 0

    # Destination should have the calls with same IDs
    dest_calls = client.server.calls_query(
        tsi.CallsQueryReq(project_id=dest_project)
    ).calls
    assert len(dest_calls) == 2
    assert {c.id for c in dest_calls} == original_ids

    # Verify data integrity
    for dest_call in dest_calls:
        assert "my_op" in dest_call.op_name
        assert dest_call.output in {2, 3}
        assert dest_call.exception is None


def test_move_calls_empty_list(client):
    """Moving an empty list of call IDs returns 0."""
    moved = client.move_calls(
        call_ids=[],
        to_project="entity/other-project",
    )
    assert moved == 0


def test_move_calls_nonexistent_ids(client):
    """Moving nonexistent call IDs returns 0."""
    moved = client.move_calls(
        call_ids=["nonexistent-id-1", "nonexistent-id-2"],
        to_project="entity/other-project",
    )
    assert moved == 0


def test_move_calls_preserves_hierarchy(client):
    """Moving parent and child calls preserves the parent-child relationship."""

    @weave.op
    def child_op(x: int) -> int:
        return x * 2

    @weave.op
    def parent_op(x: int) -> int:
        return child_op(x)

    parent_op(3)

    source_project = client._project_id()
    dest_project = source_project + "-hierarchy"

    src_calls = client.server.calls_query(
        tsi.CallsQueryReq(project_id=source_project)
    ).calls
    assert len(src_calls) == 2

    parent = next(c for c in src_calls if c.parent_id is None)
    child = next(c for c in src_calls if c.parent_id is not None)
    assert child.parent_id == parent.id

    all_ids = [c.id for c in src_calls]
    moved = client.move_calls(call_ids=all_ids, to_project=dest_project)
    assert moved == 2

    dest_calls = client.server.calls_query(
        tsi.CallsQueryReq(project_id=dest_project)
    ).calls
    assert len(dest_calls) == 2

    dest_parent = next(c for c in dest_calls if c.parent_id is None)
    dest_child = next(c for c in dest_calls if c.parent_id is not None)
    assert dest_child.parent_id == dest_parent.id
    assert dest_parent.id == parent.id
    assert dest_child.id == child.id


def test_move_calls_top_level_api(client):
    """The weave.move_calls() top-level function works."""

    @weave.op
    def greet(name: str) -> str:
        return f"hello {name}"

    greet("world")

    source_project = client._project_id()
    dest_project = source_project + "-api"

    src_calls = client.server.calls_query(
        tsi.CallsQueryReq(project_id=source_project)
    ).calls
    call_ids = [c.id for c in src_calls]

    moved = weave.move_calls(call_ids=call_ids, to_project=dest_project)
    assert moved == 1

    dest_calls = client.server.calls_query(
        tsi.CallsQueryReq(project_id=dest_project)
    ).calls
    assert len(dest_calls) == 1
    assert dest_calls[0].output == "hello world"
