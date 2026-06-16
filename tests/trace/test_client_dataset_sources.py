"""Tests for the dataset_sources provenance API.

`dataset_sources` links dataset rows (project_id + dataset_object_id +
row_digest) to their provenance sources. A source is a Weave call
(source_kind='call'), an agent span (source_kind='span'), or an agent
conversation (source_kind='conversation'). This is the second instance of the
"membership pattern" (see annotation_queue_items).

source_trace_id is part of the logical key (D1): a span's identity is
(trace_id, span_id), so two spans sharing a span_id across different traces are
distinct links. Conversations span traces and are ASSERTED (D2/D3): they carry
source_trace_id='' and skip existence validation (no backing table). A
conversation add writes BOTH the per-span links (the frozen curated subset)
AND one coarse-grain conversation link.

These tests are written against the INTERFACE SEMANTICS (the contract) and
run against ClickHouse (the only trace-server backend) via the `client`
fixture.

Notes on test data:
- Call sources: real calls are created via an @weave.op so a real call_id
  exists in calls_merged for link validation.
- Span sources: spans live in the `spans` table (populated via OTEL
  ingestion / direct insert).
- Dataset rows: links validate SOURCE existence only, NOT dataset existence.
  dataset_object_id / row_digest are opaque keys, so synthetic strings are
  fine.
"""

from __future__ import annotations

import datetime
import uuid
from typing import NamedTuple

import pytest

import weave
from tests.trace.server_utils import find_server_layer
from tests.trace.util import client_is_clickhouse
from weave.trace_server import trace_server_interface as tsi
from weave.trace_server.agents.helpers import genai_span_to_row
from weave.trace_server.agents.schema import (
    ALL_SPAN_INSERT_COLUMNS,
    AgentSpanCHInsertable,
)
from weave.trace_server.clickhouse_trace_server_batched import ClickHouseTraceServer
from weave.trace_server.errors import Error as TraceServerError

# Internal (base64) project_id the `client` fixture uses: b64("shawn/test-project").
# Used only for direct ClickHouse `spans` inserts in span-kind tests.
INTERNAL_PROJECT_ID = "c2hhd24vdGVzdC1wcm9qZWN0"


@pytest.fixture(autouse=True)
def _require_clickhouse(client):
    """dataset_sources is implemented for the ClickHouse backend only.

    The provenance layer is raw ClickHouse SQL (ReplacingMergeTree + argMax +
    bloom skip indexes) and the span-kind tests insert directly into the CH
    `spans` table, so these tests can't run on the in-memory fake backend.
    """
    if not client_is_clickhouse(client):
        pytest.skip("dataset_sources is ClickHouse-only (not on the in-memory fake)")


class CallsFixture(NamedTuple):
    call_ids: list[str]
    trace_ids: list[str]
    calls: list


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def create_test_calls(
    client, count: int, op_name_prefix: str = "ds_src_op"
) -> CallsFixture:
    """Create `count` real calls and return their ids + trace_ids."""

    @weave.op(name=f"{op_name_prefix}_{count}_{uuid.uuid4().hex[:8]}")
    def test_op(x: int) -> int:
        return x * 2

    for i in range(count):
        test_op(i)

    calls = list(client.get_calls())
    new_calls = calls[-count:] if len(calls) >= count else calls
    return CallsFixture(
        call_ids=[c.id for c in new_calls],
        trace_ids=[c.trace_id for c in new_calls],
        calls=new_calls,
    )


def call_source(call) -> tsi.SourceRef:
    """Build a call SourceRef from a Call object."""
    return tsi.SourceRef(
        source_kind=tsi.SourceKind.CALL,
        source_id=call.id,
        source_trace_id=call.trace_id,
    )


def conversation_source(conversation_id: str) -> tsi.SourceRef:
    """Build a conversation SourceRef.

    Conversations span traces, so source_trace_id is '' (conversation_id is the
    self-sufficient identity) and conversation links are asserted (no backing
    table to validate against).
    """
    return tsi.SourceRef(
        source_kind=tsi.SourceKind.CONVERSATION,
        source_id=conversation_id,
        source_trace_id="",
    )


def link_req(
    client,
    *,
    dataset_object_id: str,
    links: list[tsi.DatasetSourceLinkPayload],
    dataset_digest: str = "v0",
    include_created_status: bool = False,
) -> tsi.DatasetSourcesLinkReq:
    return tsi.DatasetSourcesLinkReq(
        project_id=client.project_id,
        dataset_object_id=dataset_object_id,
        dataset_digest=dataset_digest,
        links=links,
        include_created_status=include_created_status,
        wb_user_id="test_user",
    )


def forward_query(
    client,
    *,
    dataset_object_id: str,
    row_digests: list[str] | None = None,
    source_kinds: list[tsi.SourceKind] | None = None,
    include_deleted: bool = False,
    limit: int | None = None,
    offset: int | None = None,
) -> tsi.DatasetSourcesQueryRes:
    return client.server.dataset_sources_query(
        tsi.DatasetSourcesQueryReq(
            project_id=client.project_id,
            dataset_object_id=dataset_object_id,
            row_digests=row_digests,
            source_kinds=source_kinds,
            include_deleted=include_deleted,
            limit=limit,
            offset=offset,
        )
    )


def reverse_query(
    client, *, sources: list[tsi.SourceRef], include_deleted: bool = False
) -> tsi.SourceDatasetsQueryRes:
    return client.server.source_datasets_query(
        tsi.SourceDatasetsQueryReq(
            project_id=client.project_id,
            sources=sources,
            include_deleted=include_deleted,
        )
    )


def new_digest(prefix: str = "row") -> str:
    return f"{prefix}_{uuid.uuid4().hex}"


# ---------------------------------------------------------------------------
# Link + forward query: happy path
# ---------------------------------------------------------------------------


def test_dataset_sources_link_single_call_source_appears_in_forward_query(client):
    calls = create_test_calls(client, 1)
    call = calls.calls[0]
    ds_obj = "my_dataset_obj"
    digest = new_digest()

    res = client.server.dataset_sources_link(
        link_req(
            client,
            dataset_object_id=ds_obj,
            links=[
                tsi.DatasetSourceLinkPayload(
                    row_digest=digest, sources=[call_source(call)]
                )
            ],
        )
    )

    assert len(res.entries) == 1
    assert res.entries[0].link_id
    # include_created_status defaults to False -> created is None.
    assert res.entries[0].created is None

    fq = forward_query(client, dataset_object_id=ds_obj)
    assert len(fq.links) == 1
    link = fq.links[0]
    assert link.id == res.entries[0].link_id
    assert link.row_digest == digest
    assert link.source_kind == tsi.SourceKind.CALL
    assert link.source_id == call.id
    assert link.source_trace_id == call.trace_id
    # Cached fields are snapshotted from the source call at link time.
    assert link.source_started_at is not None
    assert link.source_display_name  # non-empty display name
    assert link.deleted_at is None


def test_dataset_sources_relink_same_tuple_yields_same_id_and_no_duplicate_rows(
    client,
):
    calls = create_test_calls(client, 1)
    call = calls.calls[0]
    ds_obj = "dedup_dataset"
    digest = new_digest()
    payload = tsi.DatasetSourceLinkPayload(
        row_digest=digest, sources=[call_source(call)]
    )

    res1 = client.server.dataset_sources_link(
        link_req(client, dataset_object_id=ds_obj, links=[payload])
    )
    res2 = client.server.dataset_sources_link(
        link_req(client, dataset_object_id=ds_obj, links=[payload])
    )
    res3 = client.server.dataset_sources_link(
        link_req(client, dataset_object_id=ds_obj, links=[payload])
    )

    # Deterministic id: same logical key -> same link_id every time.
    assert res1.entries[0].link_id == res2.entries[0].link_id
    assert res2.entries[0].link_id == res3.entries[0].link_id

    # Read-side dedup: relinking N times produces exactly one row.
    fq = forward_query(client, dataset_object_id=ds_obj)
    assert len(fq.links) == 1
    assert fq.links[0].id == res1.entries[0].link_id


def test_dataset_sources_include_created_status_new_then_relink_then_default(client):
    calls = create_test_calls(client, 1)
    call = calls.calls[0]
    ds_obj = "created_status_dataset"
    digest = new_digest()
    payload = tsi.DatasetSourceLinkPayload(
        row_digest=digest, sources=[call_source(call)]
    )

    # Brand new logical key with status requested -> created=True.
    res_new = client.server.dataset_sources_link(
        link_req(
            client,
            dataset_object_id=ds_obj,
            links=[payload],
            include_created_status=True,
        )
    )
    assert res_new.entries[0].created is True

    # Relink of an existing logical key -> created=False.
    res_relink = client.server.dataset_sources_link(
        link_req(
            client,
            dataset_object_id=ds_obj,
            links=[payload],
            include_created_status=True,
        )
    )
    assert res_relink.entries[0].created is False

    # Default (status not requested) -> created=None.
    res_default = client.server.dataset_sources_link(
        link_req(client, dataset_object_id=ds_obj, links=[payload])
    )
    assert res_default.entries[0].created is None


# ---------------------------------------------------------------------------
# Validation + atomicity
# ---------------------------------------------------------------------------


def test_dataset_sources_link_missing_call_id_errors_and_writes_nothing(client):
    calls = create_test_calls(client, 1)
    good_call = calls.calls[0]
    ds_obj = "missing_call_dataset"
    good_digest = new_digest("good")
    bad_digest = new_digest("bad")

    bad_source = tsi.SourceRef(
        source_kind=tsi.SourceKind.CALL,
        source_id="nonexistent-call-" + uuid.uuid4().hex,
        source_trace_id="nonexistent-trace",
    )

    # One good tuple and one tuple referencing a non-existent call in the
    # same batch. The whole request must fail with NO partial writes.
    with pytest.raises(TraceServerError):
        client.server.dataset_sources_link(
            link_req(
                client,
                dataset_object_id=ds_obj,
                links=[
                    tsi.DatasetSourceLinkPayload(
                        row_digest=good_digest, sources=[call_source(good_call)]
                    ),
                    tsi.DatasetSourceLinkPayload(
                        row_digest=bad_digest, sources=[bad_source]
                    ),
                ],
            )
        )

    # Neither the good tuple nor the bad tuple should have been written.
    fq = forward_query(client, dataset_object_id=ds_obj)
    assert len(fq.links) == 0


def test_dataset_sources_link_batch_cap_exceeded_errors_and_writes_nothing(client):
    calls = create_test_calls(client, 1)
    call = calls.calls[0]
    ds_obj = "batch_cap_dataset"

    # Flatten to MAX + 1 (row_digest, source) tuples: 1 source per row_digest,
    # 1001 distinct row_digests -> 1001 flattened tuples.
    cap = tsi.MAX_DATASET_SOURCE_LINKS_PER_REQUEST
    links = [
        tsi.DatasetSourceLinkPayload(
            row_digest=new_digest(f"cap{i}"), sources=[call_source(call)]
        )
        for i in range(cap + 1)
    ]

    with pytest.raises(TraceServerError):
        client.server.dataset_sources_link(
            link_req(client, dataset_object_id=ds_obj, links=links)
        )

    # Nothing written despite the request being rejected.
    fq = forward_query(client, dataset_object_id=ds_obj, limit=cap + 100)
    assert len(fq.links) == 0


# ---------------------------------------------------------------------------
# Soft delete
# ---------------------------------------------------------------------------


def test_dataset_sources_soft_delete_removes_from_forward_and_reverse(client):
    calls = create_test_calls(client, 1)
    call = calls.calls[0]
    ds_obj = "soft_delete_dataset"
    digest = new_digest()

    link_res = client.server.dataset_sources_link(
        link_req(
            client,
            dataset_object_id=ds_obj,
            links=[
                tsi.DatasetSourceLinkPayload(
                    row_digest=digest, sources=[call_source(call)]
                )
            ],
        )
    )
    link_id = link_res.entries[0].link_id

    # Present before delete.
    assert len(forward_query(client, dataset_object_id=ds_obj).links) == 1
    assert len(reverse_query(client, sources=[call_source(call)]).memberships) == 1

    del_res = client.server.dataset_sources_link_delete(
        tsi.DatasetSourcesLinkDeleteReq(
            project_id=client.project_id,
            link_ids=[link_id],
            wb_user_id="test_user",
        )
    )
    assert len(del_res.entries) == 1
    assert del_res.entries[0].link_id == link_id
    assert del_res.entries[0].deleted is True

    # Gone from forward query (include_deleted=False) and reverse query.
    assert len(forward_query(client, dataset_object_id=ds_obj).links) == 0
    assert len(reverse_query(client, sources=[call_source(call)]).memberships) == 0

    # Visible with include_deleted=True, with deleted_at set.
    fq_del = forward_query(client, dataset_object_id=ds_obj, include_deleted=True)
    assert len(fq_del.links) == 1
    assert fq_del.links[0].id == link_id
    assert fq_del.links[0].deleted_at is not None


def test_dataset_sources_delete_unknown_id_errors_and_deletes_nothing(client):
    calls = create_test_calls(client, 1)
    call = calls.calls[0]
    ds_obj = "delete_unknown_dataset"
    digest = new_digest()

    link_res = client.server.dataset_sources_link(
        link_req(
            client,
            dataset_object_id=ds_obj,
            links=[
                tsi.DatasetSourceLinkPayload(
                    row_digest=digest, sources=[call_source(call)]
                )
            ],
        )
    )
    real_link_id = link_res.entries[0].link_id

    # Batch with one real id and one unknown id -> error, no partial deletes.
    with pytest.raises(TraceServerError):
        client.server.dataset_sources_link_delete(
            tsi.DatasetSourcesLinkDeleteReq(
                project_id=client.project_id,
                link_ids=[real_link_id, "unknown-link-" + uuid.uuid4().hex],
                wb_user_id="test_user",
            )
        )

    # The real link must still be present (not partially deleted).
    assert len(forward_query(client, dataset_object_id=ds_obj).links) == 1


def test_dataset_sources_delete_already_deleted_is_idempotent_returns_false(client):
    calls = create_test_calls(client, 1)
    call = calls.calls[0]
    ds_obj = "double_delete_dataset"
    digest = new_digest()

    link_res = client.server.dataset_sources_link(
        link_req(
            client,
            dataset_object_id=ds_obj,
            links=[
                tsi.DatasetSourceLinkPayload(
                    row_digest=digest, sources=[call_source(call)]
                )
            ],
        )
    )
    link_id = link_res.entries[0].link_id

    first = client.server.dataset_sources_link_delete(
        tsi.DatasetSourcesLinkDeleteReq(
            project_id=client.project_id, link_ids=[link_id], wb_user_id="test_user"
        )
    )
    assert first.entries[0].deleted is True

    # Deleting an already-soft-deleted id is idempotent-ish: deleted=False.
    second = client.server.dataset_sources_link_delete(
        tsi.DatasetSourcesLinkDeleteReq(
            project_id=client.project_id, link_ids=[link_id], wb_user_id="test_user"
        )
    )
    assert second.entries[0].link_id == link_id
    assert second.entries[0].deleted is False


def test_dataset_sources_relink_after_delete_restores_with_same_id(client):
    calls = create_test_calls(client, 1)
    call = calls.calls[0]
    ds_obj = "restore_dataset"
    digest = new_digest()
    payload = tsi.DatasetSourceLinkPayload(
        row_digest=digest, sources=[call_source(call)]
    )

    link_res = client.server.dataset_sources_link(
        link_req(client, dataset_object_id=ds_obj, links=[payload])
    )
    link_id = link_res.entries[0].link_id

    client.server.dataset_sources_link_delete(
        tsi.DatasetSourcesLinkDeleteReq(
            project_id=client.project_id, link_ids=[link_id], wb_user_id="test_user"
        )
    )
    assert len(forward_query(client, dataset_object_id=ds_obj).links) == 0

    # Relink of a soft-deleted link is a RESTORE: same id, created=False,
    # link visible again with deleted_at=None.
    relink_res = client.server.dataset_sources_link(
        link_req(
            client,
            dataset_object_id=ds_obj,
            links=[payload],
            include_created_status=True,
        )
    )
    assert relink_res.entries[0].link_id == link_id
    assert relink_res.entries[0].created is False

    fq = forward_query(client, dataset_object_id=ds_obj)
    assert len(fq.links) == 1
    assert fq.links[0].id == link_id
    assert fq.links[0].deleted_at is None


# ---------------------------------------------------------------------------
# Conversation shape: many sources sharing one row_digest
# ---------------------------------------------------------------------------


def test_dataset_sources_conversation_five_calls_one_row_digest(client):
    calls = create_test_calls(client, 5)
    ds_obj = "conversation_dataset"
    digest = new_digest("convo")

    sources = [call_source(c) for c in calls.calls]
    res = client.server.dataset_sources_link(
        link_req(
            client,
            dataset_object_id=ds_obj,
            links=[tsi.DatasetSourceLinkPayload(row_digest=digest, sources=sources)],
        )
    )
    # 5 flattened (row_digest, source) tuples -> 5 entries.
    assert len(res.entries) == 5

    # Forward query: all 5 links returned under that one row_digest.
    fq = forward_query(client, dataset_object_id=ds_obj)
    assert len(fq.links) == 5
    assert {link.row_digest for link in fq.links} == {digest}
    assert {link.source_id for link in fq.links} == set(calls.call_ids)

    # Reverse query for one of those calls shows the dataset with that digest.
    one_call = calls.calls[0]
    rq = reverse_query(client, sources=[call_source(one_call)])
    assert len(rq.memberships) == 1
    membership = rq.memberships[0]
    assert membership.source_id == one_call.id
    assert membership.dataset_object_id == ds_obj
    assert membership.row_digests == [digest]
    assert membership.row_digests_total_count == 1
    assert membership.row_digests_truncated is False
    assert membership.first_seen_at is not None


# ---------------------------------------------------------------------------
# Reverse query: mixed batch + row_digest truncation
# ---------------------------------------------------------------------------


def test_dataset_sources_reverse_query_row_digests_truncation(client):
    calls = create_test_calls(client, 1)
    call = calls.calls[0]
    ds_obj = "truncation_dataset"

    # Link the single call to 101 distinct row_digests (101 link calls, each
    # well under the per-request cap of 1000).
    total = tsi.MAX_ROW_DIGESTS_PER_RESULT + 1  # 101
    digests = [new_digest(f"trunc{i}") for i in range(total)]
    for digest in digests:
        client.server.dataset_sources_link(
            link_req(
                client,
                dataset_object_id=ds_obj,
                links=[
                    tsi.DatasetSourceLinkPayload(
                        row_digest=digest,
                        sources=[call_source(call)],
                    )
                ],
            )
        )

    rq = reverse_query(client, sources=[call_source(call)])
    assert len(rq.memberships) == 1
    membership = rq.memberships[0]
    assert membership.row_digests_total_count == total
    assert membership.row_digests_truncated is True
    # Truncation is deterministic: the MAX_ROW_DIGESTS_PER_RESULT
    # lexicographically-smallest digests (groupArraySorted), in sorted order.
    assert membership.row_digests == sorted(digests)[: tsi.MAX_ROW_DIGESTS_PER_RESULT]


def test_dataset_sources_reverse_query_mixed_kinds_batch_no_span_error(client):
    """A reverse query may mix source kinds in one request. Querying for a
    call source plus a span source that has no links should return a single
    membership (for the call) without erroring.
    """
    calls = create_test_calls(client, 1)
    call = calls.calls[0]
    ds_obj = "mixed_reverse_dataset"
    digest = new_digest()

    client.server.dataset_sources_link(
        link_req(
            client,
            dataset_object_id=ds_obj,
            links=[
                tsi.DatasetSourceLinkPayload(
                    row_digest=digest, sources=[call_source(call)]
                )
            ],
        )
    )

    span_source = tsi.SourceRef(
        source_kind=tsi.SourceKind.SPAN,
        source_id="span-with-no-links-" + uuid.uuid4().hex,
        source_trace_id="trace-" + uuid.uuid4().hex,
    )
    rq = reverse_query(client, sources=[call_source(call), span_source])
    # Only the call has a membership; the unlinked span contributes nothing.
    assert len(rq.memberships) == 1
    assert rq.memberships[0].source_id == call.id


# ---------------------------------------------------------------------------
# Forward query filters
# ---------------------------------------------------------------------------


def test_dataset_sources_forward_query_filter_by_row_digests(client):
    calls = create_test_calls(client, 3)
    ds_obj = "row_digest_filter_dataset"
    digests = [new_digest(f"rd{i}") for i in range(3)]

    for digest, call in zip(digests, calls.calls, strict=True):
        client.server.dataset_sources_link(
            link_req(
                client,
                dataset_object_id=ds_obj,
                links=[
                    tsi.DatasetSourceLinkPayload(
                        row_digest=digest, sources=[call_source(call)]
                    )
                ],
            )
        )

    # Subset filter returns only the requested row_digests.
    subset = digests[:2]
    fq = forward_query(client, dataset_object_id=ds_obj, row_digests=subset)
    assert len(fq.links) == 2
    assert {link.row_digest for link in fq.links} == set(subset)


def test_dataset_sources_forward_query_filter_by_source_kinds(client):
    calls = create_test_calls(client, 1)
    call = calls.calls[0]
    ds_obj = "source_kind_filter_dataset"
    digest = new_digest()

    client.server.dataset_sources_link(
        link_req(
            client,
            dataset_object_id=ds_obj,
            links=[
                tsi.DatasetSourceLinkPayload(
                    row_digest=digest, sources=[call_source(call)]
                )
            ],
        )
    )

    # Filtering for 'call' kind returns the call link.
    fq_call = forward_query(
        client, dataset_object_id=ds_obj, source_kinds=[tsi.SourceKind.CALL]
    )
    assert len(fq_call.links) == 1
    assert fq_call.links[0].source_kind == tsi.SourceKind.CALL

    # Filtering for 'span' only returns nothing (no span links present).
    fq_span = forward_query(
        client, dataset_object_id=ds_obj, source_kinds=[tsi.SourceKind.SPAN]
    )
    assert len(fq_span.links) == 0


def test_dataset_sources_forward_query_limit_offset_and_ordering(client):
    calls = create_test_calls(client, 5)
    ds_obj = "pagination_dataset"

    # 5 row_digests, one call each.
    for i, call in enumerate(calls.calls):
        client.server.dataset_sources_link(
            link_req(
                client,
                dataset_object_id=ds_obj,
                links=[
                    tsi.DatasetSourceLinkPayload(
                        row_digest=new_digest(f"page{i}"),
                        sources=[call_source(call)],
                    )
                ],
            )
        )

    full = forward_query(client, dataset_object_id=ds_obj)
    assert len(full.links) == 5

    page1 = forward_query(client, dataset_object_id=ds_obj, limit=2, offset=0)
    page2 = forward_query(client, dataset_object_id=ds_obj, limit=2, offset=2)
    assert len(page1.links) == 2
    assert len(page2.links) == 2

    # Deterministic ordering: pages are disjoint and consistent with full order.
    page1_ids = [link.id for link in page1.links]
    page2_ids = [link.id for link in page2.links]
    assert set(page1_ids).isdisjoint(set(page2_ids))
    full_ids = [link.id for link in full.links]
    assert full_ids[:2] == page1_ids
    assert full_ids[2:4] == page2_ids


def test_dataset_sources_forward_query_include_deleted_flag(client):
    calls = create_test_calls(client, 2)
    ds_obj = "include_deleted_dataset"
    keep_digest = new_digest("keep")
    drop_digest = new_digest("drop")

    keep_res = client.server.dataset_sources_link(
        link_req(
            client,
            dataset_object_id=ds_obj,
            links=[
                tsi.DatasetSourceLinkPayload(
                    row_digest=keep_digest, sources=[call_source(calls.calls[0])]
                )
            ],
        )
    )
    drop_res = client.server.dataset_sources_link(
        link_req(
            client,
            dataset_object_id=ds_obj,
            links=[
                tsi.DatasetSourceLinkPayload(
                    row_digest=drop_digest, sources=[call_source(calls.calls[1])]
                )
            ],
        )
    )

    client.server.dataset_sources_link_delete(
        tsi.DatasetSourcesLinkDeleteReq(
            project_id=client.project_id,
            link_ids=[drop_res.entries[0].link_id],
            wb_user_id="test_user",
        )
    )

    # Default excludes deleted.
    fq = forward_query(client, dataset_object_id=ds_obj)
    assert {link.id for link in fq.links} == {keep_res.entries[0].link_id}

    # include_deleted returns both.
    fq_all = forward_query(client, dataset_object_id=ds_obj, include_deleted=True)
    assert {link.id for link in fq_all.links} == {
        keep_res.entries[0].link_id,
        drop_res.entries[0].link_id,
    }


# ---------------------------------------------------------------------------
# Version spanning: links are keyed by dataset_object_id, not dataset digest
# ---------------------------------------------------------------------------


def test_dataset_sources_links_span_dataset_versions(client):
    """Links are keyed by dataset_object_id (NOT the dataset content digest),
    so saving a new dataset version must not affect links. There is no
    dataset validation on link, so we model "versions" by linking the same
    dataset_object_id under two different dataset_digest values and asserting
    the forward query (keyed purely by dataset_object_id) returns both links.
    """
    calls = create_test_calls(client, 2)
    ds_obj = "versioned_dataset_obj"
    digest_a = new_digest("va")
    digest_b = new_digest("vb")

    # "Version 1" of the dataset.
    client.server.dataset_sources_link(
        link_req(
            client,
            dataset_object_id=ds_obj,
            dataset_digest="dataset_v1",
            links=[
                tsi.DatasetSourceLinkPayload(
                    row_digest=digest_a, sources=[call_source(calls.calls[0])]
                )
            ],
        )
    )
    # "Version 2" of the same dataset object (different dataset_digest).
    client.server.dataset_sources_link(
        link_req(
            client,
            dataset_object_id=ds_obj,
            dataset_digest="dataset_v2",
            links=[
                tsi.DatasetSourceLinkPayload(
                    row_digest=digest_b, sources=[call_source(calls.calls[1])]
                )
            ],
        )
    )

    # Forward query is keyed purely by dataset_object_id; both links present.
    fq = forward_query(client, dataset_object_id=ds_obj)
    assert {link.row_digest for link in fq.links} == {digest_a, digest_b}


# ---------------------------------------------------------------------------
# Span-kind sources: ClickHouse-only (the `spans` table is CH-only)
# ---------------------------------------------------------------------------


def _insert_span(client, *, span_id: str, trace_id: str, span_name: str) -> None:
    """Insert a single agent span directly into the ClickHouse `spans` table.

    Mirrors tests/trace_server/test_genai_agent_queries.py.
    """
    ch_server = find_server_layer(client.server, ClickHouseTraceServer)
    now = datetime.datetime.now(tz=datetime.timezone.utc)
    span = AgentSpanCHInsertable(
        project_id=INTERNAL_PROJECT_ID,
        trace_id=trace_id,
        span_id=span_id,
        span_name=span_name,
        started_at=now,
        ended_at=now,
        status_code="OK",
        operation_name="chat",
        agent_name="test-agent",
        provider_name="openai",
        request_model="gpt-4o",
        input_tokens=100,
        output_tokens=50,
    )
    ch_server.ch_client.insert(
        "spans",
        data=[genai_span_to_row(span)],
        column_names=ALL_SPAN_INSERT_COLUMNS,
    )


def test_dataset_sources_link_span_source_forward_query(client):
    """Span-kind source link + forward query (spans live in the `spans` table)."""
    span_id = uuid.uuid4().hex
    trace_id = uuid.uuid4().hex
    _insert_span(client, span_id=span_id, trace_id=trace_id, span_name="my-span")

    ds_obj = "span_source_dataset"
    digest = new_digest("span")
    span_source = tsi.SourceRef(
        source_kind=tsi.SourceKind.SPAN,
        source_id=span_id,
        source_trace_id=trace_id,
    )

    res = client.server.dataset_sources_link(
        link_req(
            client,
            dataset_object_id=ds_obj,
            links=[
                tsi.DatasetSourceLinkPayload(row_digest=digest, sources=[span_source])
            ],
        )
    )
    assert len(res.entries) == 1

    fq = forward_query(
        client, dataset_object_id=ds_obj, source_kinds=[tsi.SourceKind.SPAN]
    )
    assert len(fq.links) == 1
    assert fq.links[0].source_kind == tsi.SourceKind.SPAN
    assert fq.links[0].source_id == span_id
    assert fq.links[0].source_trace_id == trace_id


def test_dataset_sources_link_missing_span_errors(client):
    """Linking a span that does not exist in the project errors with no writes.
    ClickHouse-only (span validation queries the CH `spans` table).
    """
    ds_obj = "missing_span_dataset"
    digest = new_digest("missingspan")
    span_source = tsi.SourceRef(
        source_kind=tsi.SourceKind.SPAN,
        source_id="nonexistent-span-" + uuid.uuid4().hex,
        source_trace_id="nonexistent-trace-" + uuid.uuid4().hex,
    )

    with pytest.raises(TraceServerError):
        client.server.dataset_sources_link(
            link_req(
                client,
                dataset_object_id=ds_obj,
                links=[
                    tsi.DatasetSourceLinkPayload(
                        row_digest=digest, sources=[span_source]
                    )
                ],
            )
        )

    fq = forward_query(client, dataset_object_id=ds_obj)
    assert len(fq.links) == 0


# ---------------------------------------------------------------------------
# D1: source_trace_id is part of the logical key
# ---------------------------------------------------------------------------


def test_dataset_sources_same_span_id_distinct_traces_yield_distinct_links(client):
    """D1: a span's identity is (trace_id, span_id). Two spans sharing a span_id
    across different traces, linked to the SAME row_digest, are distinct links
    and must NOT collapse under the logical key. ClickHouse-only (spans table).
    """
    span_id = uuid.uuid4().hex
    trace_a = "trace-a-" + uuid.uuid4().hex
    trace_b = "trace-b-" + uuid.uuid4().hex
    _insert_span(client, span_id=span_id, trace_id=trace_a, span_name="span-a")
    _insert_span(client, span_id=span_id, trace_id=trace_b, span_name="span-b")

    ds_obj = "dup_span_id_dataset"
    digest = new_digest("dupspan")
    src_a = tsi.SourceRef(
        source_kind=tsi.SourceKind.SPAN, source_id=span_id, source_trace_id=trace_a
    )
    src_b = tsi.SourceRef(
        source_kind=tsi.SourceKind.SPAN, source_id=span_id, source_trace_id=trace_b
    )

    res = client.server.dataset_sources_link(
        link_req(
            client,
            dataset_object_id=ds_obj,
            links=[
                tsi.DatasetSourceLinkPayload(row_digest=digest, sources=[src_a, src_b])
            ],
        )
    )
    # Two distinct links (distinct ids), not one collapsed link.
    assert len(res.entries) == 2
    assert res.entries[0].link_id != res.entries[1].link_id

    fq = forward_query(
        client, dataset_object_id=ds_obj, source_kinds=[tsi.SourceKind.SPAN]
    )
    assert len(fq.links) == 2
    assert {link.source_trace_id for link in fq.links} == {trace_a, trace_b}
    assert all(link.source_id == span_id for link in fq.links)


# ---------------------------------------------------------------------------
# D2/D3: conversation is a first-class asserted source kind
# ---------------------------------------------------------------------------


def test_dataset_sources_conversation_link_round_trip_both_directions(client):
    """D2/D3: a conversation is a first-class asserted source kind. It round-trips
    through BOTH the forward (dataset->sources) and reverse (source->datasets)
    queries (no spans table needed).
    """
    conv_id = "conv-" + uuid.uuid4().hex
    ds_obj = "conversation_kind_dataset"
    digest = new_digest("conv")
    conv_src = conversation_source(conv_id)

    res = client.server.dataset_sources_link(
        link_req(
            client,
            dataset_object_id=ds_obj,
            links=[tsi.DatasetSourceLinkPayload(row_digest=digest, sources=[conv_src])],
        )
    )
    assert len(res.entries) == 1

    # Forward: dataset -> sources, filtered to the conversation kind.
    fq = forward_query(
        client, dataset_object_id=ds_obj, source_kinds=[tsi.SourceKind.CONVERSATION]
    )
    assert len(fq.links) == 1
    assert fq.links[0].source_kind == tsi.SourceKind.CONVERSATION
    assert fq.links[0].source_id == conv_id
    # Conversations carry no trace (D4 invariant).
    assert fq.links[0].source_trace_id == ""

    # Reverse: conversation -> datasets.
    rq = reverse_query(client, sources=[conv_src])
    assert len(rq.memberships) == 1
    membership = rq.memberships[0]
    assert membership.source_kind == tsi.SourceKind.CONVERSATION
    assert membership.source_id == conv_id
    assert membership.dataset_object_id == ds_obj
    assert membership.row_digests == [digest]


def test_dataset_sources_conversation_link_rejects_non_empty_trace(client):
    """D4: conversation links must carry source_trace_id='' (a conversation spans
    traces). A non-empty trace is rejected with no writes.
    """
    bad_conv = tsi.SourceRef(
        source_kind=tsi.SourceKind.CONVERSATION,
        source_id="conv-" + uuid.uuid4().hex,
        source_trace_id="should-not-be-set",
    )
    ds_obj = "conversation_bad_trace_dataset"
    digest = new_digest("convbad")

    with pytest.raises(TraceServerError):
        client.server.dataset_sources_link(
            link_req(
                client,
                dataset_object_id=ds_obj,
                links=[
                    tsi.DatasetSourceLinkPayload(row_digest=digest, sources=[bad_conv])
                ],
            )
        )

    fq = forward_query(client, dataset_object_id=ds_obj)
    assert len(fq.links) == 0


def test_dataset_sources_conversation_subset_add_freezes_sampled_spans(client):
    """D3: adding a conversation can sample a SUBSET of its spans. The frozen
    record is per-span links for exactly the sampled spans PLUS one coarse-grain
    conversation link -- never the un-sampled spans. ClickHouse-only (spans
    table). This is why model C (derive from spans WHERE conversation_id=X) is
    wrong: it would resurface the un-sampled span.
    """
    trace_id = "conv-trace-" + uuid.uuid4().hex
    conv_id = "conv-" + uuid.uuid4().hex
    span_ids = [uuid.uuid4().hex for _ in range(3)]
    for i, sid in enumerate(span_ids):
        _insert_span(client, span_id=sid, trace_id=trace_id, span_name=f"span-{i}")

    # Sample only the first two spans (the curated subset), plus the conversation.
    sampled = span_ids[:2]
    sources = [
        tsi.SourceRef(
            source_kind=tsi.SourceKind.SPAN, source_id=sid, source_trace_id=trace_id
        )
        for sid in sampled
    ] + [conversation_source(conv_id)]

    ds_obj = "conversation_subset_dataset"
    digest = new_digest("subset")
    res = client.server.dataset_sources_link(
        link_req(
            client,
            dataset_object_id=ds_obj,
            links=[tsi.DatasetSourceLinkPayload(row_digest=digest, sources=sources)],
        )
    )
    assert len(res.entries) == 3  # 2 sampled spans + 1 conversation

    fq = forward_query(client, dataset_object_id=ds_obj)
    span_links = [link for link in fq.links if link.source_kind == tsi.SourceKind.SPAN]
    conv_links = [
        link for link in fq.links if link.source_kind == tsi.SourceKind.CONVERSATION
    ]
    # Exactly the sampled spans are frozen -- the == set(sampled) below proves
    # the un-sampled third span (span_ids[2]) is absent.
    assert {link.source_id for link in span_links} == set(sampled)
    # Plus the coarse-grain conversation link.
    assert len(conv_links) == 1
    assert conv_links[0].source_id == conv_id
