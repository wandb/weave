"""Tests for Problem 1: Version Index Stability on Re-publish.

Tests two changes:
1. version_index ordering uses min(created_at) (first appearance) instead of
   created_at (surviving row), with digest ASC as tiebreaker.
2. obj_create dedup-before-insert: skips INSERT if a non-deleted row with the
   same digest already exists.
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


def _obj_create(client: WeaveClient, object_id: str, val: dict) -> tsi.ObjCreateRes:
    return client.server.obj_create(
        tsi.ObjCreateReq(
            obj=tsi.ObjSchemaForInsert(
                project_id=client._project_id(),
                object_id=object_id,
                val=val,
            )
        )
    )


def _obj_delete(client: WeaveClient, object_id: str, digests: list[str]) -> int:
    return client.server.obj_delete(
        tsi.ObjDeleteReq(
            project_id=client._project_id(),
            object_id=object_id,
            digests=digests,
        )
    ).num_deleted


def _assert_version(obj: tsi.ObjSchema, expected_index: int, expected_digest: str) -> None:
    assert obj.version_index == expected_index
    assert obj.digest == expected_digest


def _get_latest(client: WeaveClient, object_id: str) -> tsi.ObjSchema | None:
    resp = client.server.objs_query(
        tsi.ObjQueryReq(
            project_id=client._project_id(),
            filter=tsi.ObjectVersionFilter(
                object_ids=[object_id], latest_only=True
            ),
        )
    )
    return resp.objs[0] if resp.objs else None


# ── Version index stability on re-publish ────────────────────────────


def test_republish_oldest_version_index_stable(client: WeaveClient):
    """Re-publishing A (v0) when latest=C should not shift indices."""
    v0 = weave.publish({"text": "A"}, name="idx_stable_1")
    v1 = weave.publish({"text": "B"}, name="idx_stable_1")
    v2 = weave.publish({"text": "C"}, name="idx_stable_1")

    weave.publish({"text": "A"}, name="idx_stable_1")

    objs = _objs_query(client, "idx_stable_1")
    assert len(objs) == 3, f"Expected 3 versions, got {len(objs)}"

    _assert_version(objs[0], 0, v0.digest)
    _assert_version(objs[1], 1, v1.digest)
    _assert_version(objs[2], 2, v2.digest)

    latest = _get_latest(client, "idx_stable_1")
    assert latest is not None
    assert latest.digest == v2.digest, "Latest should still be C"


def test_republish_middle_version_index_stable(client: WeaveClient):
    """Re-publishing B (v1) when latest=C should not shift indices."""
    v0 = weave.publish({"text": "A"}, name="idx_stable_2")
    v1 = weave.publish({"text": "B"}, name="idx_stable_2")
    v2 = weave.publish({"text": "C"}, name="idx_stable_2")

    weave.publish({"text": "B"}, name="idx_stable_2")

    objs = _objs_query(client, "idx_stable_2")
    assert len(objs) == 3

    _assert_version(objs[0], 0, v0.digest)
    _assert_version(objs[1], 1, v1.digest)
    _assert_version(objs[2], 2, v2.digest)

    latest = _get_latest(client, "idx_stable_2")
    assert latest.digest == v2.digest


def test_republish_latest_version_index_stable(client: WeaveClient):
    """Re-publishing C (latest) should be a complete no-op."""
    v0 = weave.publish({"text": "A"}, name="idx_stable_3")
    v1 = weave.publish({"text": "B"}, name="idx_stable_3")
    v2 = weave.publish({"text": "C"}, name="idx_stable_3")

    weave.publish({"text": "C"}, name="idx_stable_3")

    objs = _objs_query(client, "idx_stable_3")
    assert len(objs) == 3

    _assert_version(objs[0], 0, v0.digest)
    _assert_version(objs[1], 1, v1.digest)
    _assert_version(objs[2], 2, v2.digest)


def test_delete_middle_republish_version_index_stable(client: WeaveClient):
    """Delete B, then re-publish B. Known gap on ClickHouse: B's new row has
    a newer created_at, so after ReplacingMergeTree merge min(created_at) shifts.
    A and C indices should remain stable regardless.
    """
    v0 = weave.publish({"text": "A"}, name="idx_stable_4")
    v1 = weave.publish({"text": "B"}, name="idx_stable_4")
    v2 = weave.publish({"text": "C"}, name="idx_stable_4")

    _obj_delete(client, "idx_stable_4", [v1.digest])

    weave.publish({"text": "B"}, name="idx_stable_4")

    objs = _objs_query(client, "idx_stable_4")
    non_deleted = [o for o in objs if o.deleted_at is None]
    assert len(non_deleted) == 3

    a = next(o for o in non_deleted if o.digest == v0.digest)
    c = next(o for o in non_deleted if o.digest == v2.digest)
    assert a.version_index == 0
    assert c.version_index == 2


def test_five_versions_republish_v0_stable(client: WeaveClient):
    """With 5 versions (A-E), re-publishing A should not shift any indices."""
    refs = {}
    for label in ["A", "B", "C", "D", "E"]:
        refs[label] = weave.publish({"text": label}, name="idx_stable_5")

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


def test_republish_two_versions_indices_stable(client: WeaveClient):
    """Re-publishing A then B back-to-back should not scramble indices."""
    v0 = weave.publish({"text": "A"}, name="idx_stable_6")
    v1 = weave.publish({"text": "B"}, name="idx_stable_6")
    v2 = weave.publish({"text": "C"}, name="idx_stable_6")

    weave.publish({"text": "A"}, name="idx_stable_6")
    weave.publish({"text": "B"}, name="idx_stable_6")

    objs = _objs_query(client, "idx_stable_6")
    assert len(objs) == 3

    _assert_version(objs[0], 0, v0.digest)
    _assert_version(objs[1], 1, v1.digest)
    _assert_version(objs[2], 2, v2.digest)

    latest = _get_latest(client, "idx_stable_6")
    assert latest.digest == v2.digest


# ── Dedup-before-insert ──────────────────────────────────────────────


def test_dedup_skips_insert_on_existing_digest(client: WeaveClient):
    """obj_create with an existing non-deleted digest should not create a new row."""
    r1 = _obj_create(client, "dedup_1", {"value": "same"})
    r2 = _obj_create(client, "dedup_1", {"value": "same"})

    assert r1.digest == r2.digest

    objs = _objs_query(client, "dedup_1")
    assert len(objs) == 1, f"Dedup should prevent duplicate row, got {len(objs)}"
    assert objs[0].version_index == 0


def test_dedup_allows_insert_after_delete(client: WeaveClient):
    """obj_create should insert if the same digest was previously deleted."""
    r1 = _obj_create(client, "dedup_2", {"value": "deleteme"})
    _obj_delete(client, "dedup_2", [r1.digest])

    # Re-create same content — should insert since the existing row is deleted
    r2 = _obj_create(client, "dedup_2", {"value": "deleteme"})
    assert r2.digest == r1.digest

    objs = _objs_query(client, "dedup_2")
    non_deleted = [o for o in objs if o.deleted_at is None]
    assert len(non_deleted) >= 1, "Should have at least one non-deleted row"


def test_dedup_different_content_creates_new_version(client: WeaveClient):
    """Different content should always create a new version."""
    r1 = _obj_create(client, "dedup_3", {"value": "first"})
    r2 = _obj_create(client, "dedup_3", {"value": "second"})

    assert r1.digest != r2.digest

    objs = _objs_query(client, "dedup_3")
    assert len(objs) == 2
    assert objs[0].version_index == 0
    assert objs[1].version_index == 1


def test_dedup_returns_correct_digest(client: WeaveClient):
    """obj_create on a dedup hit should still return the correct digest."""
    r1 = _obj_create(client, "dedup_4", {"value": "hello"})
    _obj_create(client, "dedup_4", {"value": "world"})

    # Re-publish first version
    r3 = _obj_create(client, "dedup_4", {"value": "hello"})
    assert r3.digest == r1.digest
    assert r3.object_id == "dedup_4"


def test_dedup_across_different_objects(client: WeaveClient):
    """Same content under different object_ids should not dedup."""
    r1 = _obj_create(client, "dedup_5a", {"value": "shared"})
    r2 = _obj_create(client, "dedup_5b", {"value": "shared"})

    # Same digest (same content), but different objects — both should exist
    objs_a = _objs_query(client, "dedup_5a")
    objs_b = _objs_query(client, "dedup_5b")
    assert len(objs_a) == 1
    assert len(objs_b) == 1


def test_version_index_sequential_after_many_creates(client: WeaveClient):
    """Version indices should be sequential 0..N-1 for N unique versions."""
    n = 20
    for i in range(n):
        _obj_create(client, "seq_idx", {"version": i})

    objs = _objs_query(client, "seq_idx")
    assert len(objs) == n
    for i, obj in enumerate(objs):
        assert obj.version_index == i, (
            f"Expected version_index={i}, got {obj.version_index}"
        )


def test_delete_preserves_version_indices(client: WeaveClient):
    """Deleting a version should not shift other versions' indices."""
    r0 = _obj_create(client, "del_idx", {"v": 0})
    r1 = _obj_create(client, "del_idx", {"v": 1})
    r2 = _obj_create(client, "del_idx", {"v": 2})

    _obj_delete(client, "del_idx", [r1.digest])

    objs = _objs_query(client, "del_idx")
    non_deleted = [o for o in objs if o.deleted_at is None]
    assert len(non_deleted) == 2

    a = next(o for o in non_deleted if o.digest == r0.digest)
    c = next(o for o in non_deleted if o.digest == r2.digest)
    assert a.version_index == 0, "v0 should stay at 0 after deleting v1"
    assert c.version_index == 2, "v2 should stay at 2 after deleting v1"
