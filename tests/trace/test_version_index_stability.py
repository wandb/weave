"""Reproduction tests for Problem 1: Version Index Instability on Re-publish.

Root cause: In ClickHouse, version_index is computed via
    ROW_NUMBER() OVER (PARTITION BY ... ORDER BY created_at ASC) - 1
When the same digest is re-published, a new row with a newer created_at is
inserted. The dedup query keeps the latest row per digest, but that row now
has a newer timestamp, shifting it to the end of the ordering.

SQLite is not affected because obj_create checks _obj_exists and returns
early when the same digest already exists (no new row is created).
"""

import weave
from weave.trace.weave_client import WeaveClient
from weave.trace_server import trace_server_interface as tsi
from weave.trace_server.common_interface import SortBy


def _objs_query(client: WeaveClient, object_id: str) -> list[tsi.ObjSchema]:
    objs = client.server.objs_query(
        tsi.ObjQueryReq(
            project_id=client._project_id(),
            filter=tsi.ObjectVersionFilter(object_ids=[object_id]),
            sort_by=[SortBy(field="created_at", direction="asc")],
        )
    )
    return objs.objs


def _obj_delete(client: WeaveClient, object_id: str, digests: list[str]) -> int:
    return client.server.obj_delete(
        tsi.ObjDeleteReq(
            project_id=client._project_id(),
            object_id=object_id,
            digests=digests,
        )
    ).num_deleted


def _get_latest(client: WeaveClient, object_id: str) -> tsi.ObjSchema | None:
    resp = client.server.objs_query(
        tsi.ObjQueryReq(
            project_id=client._project_id(),
            filter=tsi.ObjectVersionFilter(object_ids=[object_id], latest_only=True),
        )
    )
    return resp.objs[0] if resp.objs else None


# ── P1-T1: Re-publish oldest version ────────────────────────────────


def test_republish_oldest_version_index_stable(client: WeaveClient):
    """Re-publishing A (v0) when latest=C should be a no-op on indices.

    Before:  A=v0, B=v1, C=v2  latest=C
    After:   A=v0, B=v1, C=v2  latest=C  (expected)
    Bug:     B=v0, C=v1, A=v2  latest=A  (actual on ClickHouse)
    """
    v0 = weave.publish({"text": "A"}, name="idx_stable_1")
    v1 = weave.publish({"text": "B"}, name="idx_stable_1")
    v2 = weave.publish({"text": "C"}, name="idx_stable_1")

    # Re-publish A (same content as v0)
    weave.publish({"text": "A"}, name="idx_stable_1")

    objs = _objs_query(client, "idx_stable_1")
    assert len(objs) == 3, f"Expected 3 versions, got {len(objs)}"

    assert objs[0].digest == v0.digest
    assert objs[0].version_index == 0
    assert objs[1].digest == v1.digest
    assert objs[1].version_index == 1
    assert objs[2].digest == v2.digest
    assert objs[2].version_index == 2

    latest = _get_latest(client, "idx_stable_1")
    assert latest is not None
    assert latest.digest == v2.digest, "Latest should still be C"


# ── P1-T2: Re-publish middle version ────────────────────────────────


def test_republish_middle_version_index_stable(client: WeaveClient):
    """Re-publishing B (v1) when latest=C should be a no-op on indices."""
    v0 = weave.publish({"text": "A"}, name="idx_stable_2")
    v1 = weave.publish({"text": "B"}, name="idx_stable_2")
    v2 = weave.publish({"text": "C"}, name="idx_stable_2")

    # Re-publish B (same content as v1)
    weave.publish({"text": "B"}, name="idx_stable_2")

    objs = _objs_query(client, "idx_stable_2")
    assert len(objs) == 3

    assert objs[0].version_index == 0
    assert objs[0].digest == v0.digest
    assert objs[1].version_index == 1
    assert objs[1].digest == v1.digest
    assert objs[2].version_index == 2
    assert objs[2].digest == v2.digest

    latest = _get_latest(client, "idx_stable_2")
    assert latest.digest == v2.digest


# ── P1-T3: Re-publish latest version (should always be no-op) ───────


def test_republish_latest_version_index_stable(client: WeaveClient):
    """Re-publishing C (latest) should be a complete no-op."""
    v0 = weave.publish({"text": "A"}, name="idx_stable_3")
    v1 = weave.publish({"text": "B"}, name="idx_stable_3")
    v2 = weave.publish({"text": "C"}, name="idx_stable_3")

    weave.publish({"text": "C"}, name="idx_stable_3")

    objs = _objs_query(client, "idx_stable_3")
    assert len(objs) == 3

    assert objs[0].version_index == 0
    assert objs[0].digest == v0.digest
    assert objs[1].version_index == 1
    assert objs[1].digest == v1.digest
    assert objs[2].version_index == 2
    assert objs[2].digest == v2.digest


# ── P1-T4: Delete middle, re-publish middle ─────────────────────────


def test_delete_middle_republish_version_index_stable(client: WeaveClient):
    """Delete B, then re-publish B. B should return at v1, not shift to end."""
    v0 = weave.publish({"text": "A"}, name="idx_stable_4")
    v1 = weave.publish({"text": "B"}, name="idx_stable_4")
    v2 = weave.publish({"text": "C"}, name="idx_stable_4")

    _obj_delete(client, "idx_stable_4", [v1.digest])

    # Re-publish B (undelete / re-create)
    weave.publish({"text": "B"}, name="idx_stable_4")

    objs = _objs_query(client, "idx_stable_4")
    non_deleted = [o for o in objs if o.deleted_at is None]
    assert len(non_deleted) == 3

    # A should still be v0, C should still be v2
    a = next(o for o in non_deleted if o.digest == v0.digest)
    c = next(o for o in non_deleted if o.digest == v2.digest)
    assert a.version_index == 0
    assert c.version_index == 2


# ── P1-T5: 5 versions, re-publish v0 ────────────────────────────────


def test_five_versions_republish_v0_stable(client: WeaveClient):
    """With 5 versions (A-E), re-publishing A should not shift any indices."""
    refs = {}
    for label in ["A", "B", "C", "D", "E"]:
        refs[label] = weave.publish({"text": label}, name="idx_stable_5")

    # Re-publish A
    weave.publish({"text": "A"}, name="idx_stable_5")

    objs = _objs_query(client, "idx_stable_5")
    assert len(objs) == 5

    for i, label in enumerate(["A", "B", "C", "D", "E"]):
        assert objs[i].version_index == i, (
            f"{label}: expected v{i}, got v{objs[i].version_index}"
        )
        assert objs[i].digest == refs[label].digest

    latest = _get_latest(client, "idx_stable_5")
    assert latest.digest == refs["E"].digest, "Latest should still be E"


# ── P1-T6: Re-publish A then B back-to-back ─────────────────────────


def test_republish_two_versions_indices_stable(client: WeaveClient):
    """Re-publishing A then B should not scramble any indices."""
    v0 = weave.publish({"text": "A"}, name="idx_stable_6")
    v1 = weave.publish({"text": "B"}, name="idx_stable_6")
    v2 = weave.publish({"text": "C"}, name="idx_stable_6")

    weave.publish({"text": "A"}, name="idx_stable_6")
    weave.publish({"text": "B"}, name="idx_stable_6")

    objs = _objs_query(client, "idx_stable_6")
    assert len(objs) == 3

    assert objs[0].version_index == 0
    assert objs[0].digest == v0.digest
    assert objs[1].version_index == 1
    assert objs[1].digest == v1.digest
    assert objs[2].version_index == 2
    assert objs[2].digest == v2.digest

    latest = _get_latest(client, "idx_stable_6")
    assert latest.digest == v2.digest
