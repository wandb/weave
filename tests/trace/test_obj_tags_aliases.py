import pytest
from pydantic import ValidationError

import weave
from weave.trace.weave_client import WeaveClient
from weave.trace_server import trace_server_interface as tsi
from weave.trace_server.errors import NotFoundError


def _publish_obj(client: WeaveClient, name: str, val: dict | None = None):
    """Publish an object and return (object_id, digest)."""
    weave.publish(val or {"data": "test"}, name=name)
    res = client.server.objs_query(
        tsi.ObjQueryReq(
            project_id=client._project_id(),
            filter=tsi.ObjectVersionFilter(object_ids=[name]),
        )
    )
    obj = res.objs[-1]  # latest version
    return obj.object_id, obj.digest


# --- Tag CRUD ---


def test_add_tags(client: WeaveClient):
    object_id, digest = _publish_obj(client, "tag_obj")

    client.server.obj_add_tags(
        tsi.ObjAddTagsReq(
            project_id=client._project_id(),
            object_id=object_id,
            digest=digest,
            tags=["reviewed", "staging"],
        )
    )

    res = client.server.objs_query(
        tsi.ObjQueryReq(
            project_id=client._project_id(),
            filter=tsi.ObjectVersionFilter(object_ids=[object_id]),
            include_tags_and_aliases=True,
        )
    )
    assert sorted(res.objs[0].tags) == ["reviewed", "staging"]


def test_remove_tags(client: WeaveClient):
    object_id, digest = _publish_obj(client, "tag_rm_obj")

    client.server.obj_add_tags(
        tsi.ObjAddTagsReq(
            project_id=client._project_id(),
            object_id=object_id,
            digest=digest,
            tags=["a", "b"],
        )
    )
    client.server.obj_remove_tags(
        tsi.ObjRemoveTagsReq(
            project_id=client._project_id(),
            object_id=object_id,
            digest=digest,
            tags=["a"],
        )
    )

    res = client.server.objs_query(
        tsi.ObjQueryReq(
            project_id=client._project_id(),
            filter=tsi.ObjectVersionFilter(object_ids=[object_id]),
            include_tags_and_aliases=True,
        )
    )
    assert res.objs[0].tags == ["b"]


def test_add_tags_idempotent(client: WeaveClient):
    object_id, digest = _publish_obj(client, "tag_idem_obj")

    for _ in range(3):
        client.server.obj_add_tags(
            tsi.ObjAddTagsReq(
                project_id=client._project_id(),
                object_id=object_id,
                digest=digest,
                tags=["dup-tag"],
            )
        )

    res = client.server.objs_query(
        tsi.ObjQueryReq(
            project_id=client._project_id(),
            filter=tsi.ObjectVersionFilter(object_ids=[object_id]),
            include_tags_and_aliases=True,
        )
    )
    assert res.objs[0].tags == ["dup-tag"]


def test_remove_tags_nonexistent(client: WeaveClient):
    object_id, digest = _publish_obj(client, "tag_nonexist_obj")

    # Should succeed silently — no error
    client.server.obj_remove_tags(
        tsi.ObjRemoveTagsReq(
            project_id=client._project_id(),
            object_id=object_id,
            digest=digest,
            tags=["never-added"],
        )
    )


# --- Alias CRUD ---


def test_set_alias(client: WeaveClient):
    object_id, digest = _publish_obj(client, "alias_obj")

    client.server.obj_set_alias(
        tsi.ObjSetAliasReq(
            project_id=client._project_id(),
            object_id=object_id,
            digest=digest,
            alias="production",
        )
    )

    res = client.server.objs_query(
        tsi.ObjQueryReq(
            project_id=client._project_id(),
            filter=tsi.ObjectVersionFilter(object_ids=[object_id]),
            include_tags_and_aliases=True,
        )
    )
    assert "production" in res.objs[0].aliases


def test_set_alias_reassignment(client: WeaveClient):
    """Setting an alias on v1 should move it away from v0."""
    weave.publish({"v": 0}, name="alias_reassign")
    weave.publish({"v": 1}, name="alias_reassign")

    res = client.server.objs_query(
        tsi.ObjQueryReq(
            project_id=client._project_id(),
            filter=tsi.ObjectVersionFilter(object_ids=["alias_reassign"]),
        )
    )
    objs = sorted(res.objs, key=lambda o: o.version_index)
    v0, v1 = objs[0], objs[1]

    # Set alias on v0
    client.server.obj_set_alias(
        tsi.ObjSetAliasReq(
            project_id=client._project_id(),
            object_id=v0.object_id,
            digest=v0.digest,
            alias="staging",
        )
    )

    # Move alias to v1
    client.server.obj_set_alias(
        tsi.ObjSetAliasReq(
            project_id=client._project_id(),
            object_id=v1.object_id,
            digest=v1.digest,
            alias="staging",
        )
    )

    res = client.server.objs_query(
        tsi.ObjQueryReq(
            project_id=client._project_id(),
            filter=tsi.ObjectVersionFilter(object_ids=["alias_reassign"]),
            include_tags_and_aliases=True,
        )
    )
    objs = sorted(res.objs, key=lambda o: o.version_index)
    assert "staging" not in (objs[0].aliases or [])
    assert "staging" in objs[1].aliases


def test_remove_alias(client: WeaveClient):
    object_id, digest = _publish_obj(client, "alias_rm_obj")

    client.server.obj_set_alias(
        tsi.ObjSetAliasReq(
            project_id=client._project_id(),
            object_id=object_id,
            digest=digest,
            alias="temp-alias",
        )
    )
    client.server.obj_remove_alias(
        tsi.ObjRemoveAliasReq(
            project_id=client._project_id(),
            object_id=object_id,
            alias="temp-alias",
        )
    )

    res = client.server.objs_query(
        tsi.ObjQueryReq(
            project_id=client._project_id(),
            filter=tsi.ObjectVersionFilter(object_ids=[object_id]),
            include_tags_and_aliases=True,
        )
    )
    assert "temp-alias" not in (res.objs[0].aliases or [])


def test_remove_alias_nonexistent(client: WeaveClient):
    object_id, _ = _publish_obj(client, "alias_nonexist_obj")

    # Should succeed silently
    client.server.obj_remove_alias(
        tsi.ObjRemoveAliasReq(
            project_id=client._project_id(),
            object_id=object_id,
            alias="no-such-alias",
        )
    )


# --- Validation ---


def test_alias_reserved_names():
    """'latest' and version-like names like 'v0' should be rejected at the request level."""
    with pytest.raises(ValidationError):
        tsi.ObjSetAliasReq(
            project_id="test/proj",
            object_id="obj",
            digest="abc123",
            alias="latest",
        )

    with pytest.raises(ValidationError):
        tsi.ObjSetAliasReq(
            project_id="test/proj",
            object_id="obj",
            digest="abc123",
            alias="v0",
        )

    with pytest.raises(ValidationError):
        tsi.ObjSetAliasReq(
            project_id="test/proj",
            object_id="obj",
            digest="abc123",
            alias="v123",
        )


def test_tag_validation():
    """Empty, too-long, and special-char names rejected."""
    # Empty tag
    with pytest.raises(ValidationError):
        tsi.ObjAddTagsReq(
            project_id="test/proj",
            object_id="obj",
            digest="abc123",
            tags=[""],
        )

    # Too long (>128 chars)
    with pytest.raises(ValidationError):
        tsi.ObjAddTagsReq(
            project_id="test/proj",
            object_id="obj",
            digest="abc123",
            tags=["a" * 129],
        )

    # Special characters
    with pytest.raises(ValidationError):
        tsi.ObjAddTagsReq(
            project_id="test/proj",
            object_id="obj",
            digest="abc123",
            tags=["invalid tag!"],
        )


# --- Virtual "latest" alias ---


def test_latest_virtual_alias(client: WeaveClient):
    """The latest version should have 'latest' in its aliases; earlier versions should not."""
    weave.publish({"v": 0}, name="latest_test")
    weave.publish({"v": 1}, name="latest_test")

    res = client.server.objs_query(
        tsi.ObjQueryReq(
            project_id=client._project_id(),
            filter=tsi.ObjectVersionFilter(object_ids=["latest_test"]),
            include_tags_and_aliases=True,
        )
    )
    objs = sorted(res.objs, key=lambda o: o.version_index)
    assert "latest" not in (objs[0].aliases or [])
    assert "latest" in objs[1].aliases


# --- Query filtering ---


def test_objs_query_filter_by_tags(client: WeaveClient):
    object_id, digest = _publish_obj(client, "filter_tag_obj")
    _publish_obj(client, "filter_tag_other")

    client.server.obj_add_tags(
        tsi.ObjAddTagsReq(
            project_id=client._project_id(),
            object_id=object_id,
            digest=digest,
            tags=["special"],
        )
    )

    res = client.server.objs_query(
        tsi.ObjQueryReq(
            project_id=client._project_id(),
            filter=tsi.ObjectVersionFilter(tags=["special"]),
        )
    )
    assert len(res.objs) == 1
    assert res.objs[0].object_id == object_id


def test_objs_query_filter_by_aliases(client: WeaveClient):
    object_id, digest = _publish_obj(client, "filter_alias_obj")
    _publish_obj(client, "filter_alias_other")

    client.server.obj_set_alias(
        tsi.ObjSetAliasReq(
            project_id=client._project_id(),
            object_id=object_id,
            digest=digest,
            alias="production",
        )
    )

    res = client.server.objs_query(
        tsi.ObjQueryReq(
            project_id=client._project_id(),
            filter=tsi.ObjectVersionFilter(aliases=["production"]),
        )
    )
    assert len(res.objs) == 1
    assert res.objs[0].object_id == object_id


# --- Alias resolution in obj_read ---


def test_alias_resolution_in_obj_read(client: WeaveClient):
    """obj_read with digest='production' should resolve the alias to the actual digest."""
    object_id, digest = _publish_obj(client, "resolve_alias_obj")

    client.server.obj_set_alias(
        tsi.ObjSetAliasReq(
            project_id=client._project_id(),
            object_id=object_id,
            digest=digest,
            alias="production",
        )
    )

    res = client.server.obj_read(
        tsi.ObjReadReq(
            project_id=client._project_id(),
            object_id=object_id,
            digest="production",
            include_tags_and_aliases=True,
        )
    )
    assert res.obj.digest == digest
    assert "production" in res.obj.aliases


# --- Error cases ---


def test_tags_on_nonexistent_object(client: WeaveClient):
    with pytest.raises(NotFoundError):
        client.server.obj_add_tags(
            tsi.ObjAddTagsReq(
                project_id=client._project_id(),
                object_id="nonexistent_object",
                digest="0000000000000000000000000000000000000000000000000000000000000000",
                tags=["tag"],
            )
        )
