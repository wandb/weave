import pytest
from pydantic import ValidationError

import weave
from weave.trace.weave_client import WeaveClient
from weave.trace_server import trace_server_interface as tsi
from weave.trace_server.errors import NotFoundError
from weave.trace_server.trace_server_common import digest_is_content_hash


def _publish_obj(client: WeaveClient, name: str, val: dict | None = None):
    """Publish an object and return (object_id, digest)."""
    weave.publish(val or {"data": "test"}, name=name)
    res = client.server.objs_query(
        tsi.ObjQueryReq(
            project_id=client._project_id(),
            filter=tsi.ObjectVersionFilter(object_ids=[name]),
            sort_by=[tsi.SortBy(field="created_at", direction="asc")],
        )
    )
    obj = res.objs[-1]  # latest version (sorted by created_at asc)
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
    """Empty and too-long tag names rejected. Tags are permissive otherwise."""
    # Empty tag
    with pytest.raises(ValidationError):
        tsi.ObjAddTagsReq(
            project_id="test/proj",
            object_id="obj",
            digest="abc123",
            tags=[""],
        )

    # Too long (>256 chars)
    with pytest.raises(ValidationError):
        tsi.ObjAddTagsReq(
            project_id="test/proj",
            object_id="obj",
            digest="abc123",
            tags=["a" * 257],
        )

    # Special characters ARE allowed for tags (permissive like W&B Models)
    tsi.ObjAddTagsReq(
        project_id="test/proj",
        object_id="obj",
        digest="abc123",
        tags=["has spaces", "special!chars", "emoji-ok"],
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


def test_alias_on_nonexistent_object(client: WeaveClient):
    with pytest.raises(NotFoundError):
        client.server.obj_set_alias(
            tsi.ObjSetAliasReq(
                project_id=client._project_id(),
                object_id="nonexistent_object",
                digest="0000000000000000000000000000000000000000000000000000000000000000",
                alias="prod",
            )
        )


# --- Enrichment behavior ---


def test_include_tags_and_aliases_false_returns_none(client: WeaveClient):
    """When include_tags_and_aliases is not set, tags/aliases should be None."""
    object_id, digest = _publish_obj(client, "no_enrich_obj")

    client.server.obj_add_tags(
        tsi.ObjAddTagsReq(
            project_id=client._project_id(),
            object_id=object_id,
            digest=digest,
            tags=["some-tag"],
        )
    )

    # Query without include_tags_and_aliases
    res = client.server.objs_query(
        tsi.ObjQueryReq(
            project_id=client._project_id(),
            filter=tsi.ObjectVersionFilter(object_ids=[object_id]),
        )
    )
    assert res.objs[0].tags is None
    assert res.objs[0].aliases is None

    # obj_read without include_tags_and_aliases
    read_res = client.server.obj_read(
        tsi.ObjReadReq(
            project_id=client._project_id(),
            object_id=object_id,
            digest=digest,
        )
    )
    assert read_res.obj.tags is None
    assert read_res.obj.aliases is None


def test_obj_read_enrichment(client: WeaveClient):
    """obj_read with include_tags_and_aliases returns tags and aliases."""
    object_id, digest = _publish_obj(client, "read_enrich_obj")

    client.server.obj_add_tags(
        tsi.ObjAddTagsReq(
            project_id=client._project_id(),
            object_id=object_id,
            digest=digest,
            tags=["reviewed"],
        )
    )
    client.server.obj_set_alias(
        tsi.ObjSetAliasReq(
            project_id=client._project_id(),
            object_id=object_id,
            digest=digest,
            alias="prod",
        )
    )

    res = client.server.obj_read(
        tsi.ObjReadReq(
            project_id=client._project_id(),
            object_id=object_id,
            digest=digest,
            include_tags_and_aliases=True,
        )
    )
    assert res.obj.tags == ["reviewed"]
    assert "prod" in res.obj.aliases
    assert "latest" in res.obj.aliases


# --- Tag version scoping ---


def test_tags_scoped_to_version(client: WeaveClient):
    """Tags on v0 should not appear on v1."""
    weave.publish({"v": 0}, name="tag_scope_obj")
    weave.publish({"v": 1}, name="tag_scope_obj")

    res = client.server.objs_query(
        tsi.ObjQueryReq(
            project_id=client._project_id(),
            filter=tsi.ObjectVersionFilter(object_ids=["tag_scope_obj"]),
            sort_by=[tsi.SortBy(field="created_at", direction="asc")],
        )
    )
    v0, v1 = res.objs[0], res.objs[1]

    # Tag only v0
    client.server.obj_add_tags(
        tsi.ObjAddTagsReq(
            project_id=client._project_id(),
            object_id=v0.object_id,
            digest=v0.digest,
            tags=["v0-only"],
        )
    )

    res = client.server.objs_query(
        tsi.ObjQueryReq(
            project_id=client._project_id(),
            filter=tsi.ObjectVersionFilter(object_ids=["tag_scope_obj"]),
            include_tags_and_aliases=True,
            sort_by=[tsi.SortBy(field="created_at", direction="asc")],
        )
    )
    assert "v0-only" in res.objs[0].tags
    assert res.objs[1].tags == []


def test_multiple_aliases_on_object(client: WeaveClient):
    """Different aliases can point to different versions of the same object."""
    weave.publish({"v": 0}, name="multi_alias_obj")
    weave.publish({"v": 1}, name="multi_alias_obj")

    res = client.server.objs_query(
        tsi.ObjQueryReq(
            project_id=client._project_id(),
            filter=tsi.ObjectVersionFilter(object_ids=["multi_alias_obj"]),
            sort_by=[tsi.SortBy(field="created_at", direction="asc")],
        )
    )
    v0, v1 = res.objs[0], res.objs[1]

    client.server.obj_set_alias(
        tsi.ObjSetAliasReq(
            project_id=client._project_id(),
            object_id=v0.object_id,
            digest=v0.digest,
            alias="stable",
        )
    )
    client.server.obj_set_alias(
        tsi.ObjSetAliasReq(
            project_id=client._project_id(),
            object_id=v1.object_id,
            digest=v1.digest,
            alias="canary",
        )
    )

    res = client.server.objs_query(
        tsi.ObjQueryReq(
            project_id=client._project_id(),
            filter=tsi.ObjectVersionFilter(object_ids=["multi_alias_obj"]),
            include_tags_and_aliases=True,
            sort_by=[tsi.SortBy(field="created_at", direction="asc")],
        )
    )
    assert "stable" in res.objs[0].aliases
    assert "canary" not in (res.objs[0].aliases or [])
    assert "canary" in res.objs[1].aliases
    assert "stable" not in (res.objs[1].aliases or [])


# --- obj_read with real digest (not alias) ---


def test_obj_read_with_real_digest(client: WeaveClient):
    """obj_read with a content-addressed digest should not attempt alias resolution."""
    object_id, digest = _publish_obj(client, "real_digest_obj")

    res = client.server.obj_read(
        tsi.ObjReadReq(
            project_id=client._project_id(),
            object_id=object_id,
            digest=digest,
        )
    )
    assert res.obj.digest == digest
    assert res.obj.object_id == object_id


# --- Validation: accepted names ---


def test_valid_tag_and_alias_names():
    """Tags are very permissive; aliases disallow only '/' and ':'."""
    # Tags: permissive — spaces, special chars, up to 256 chars
    tsi.ObjAddTagsReq(
        project_id="test/proj",
        object_id="obj",
        digest="abc123",
        tags=[
            "reviewed",
            "my-tag",
            "my_tag",
            "my.tag",
            "Tag123",
            "a" * 256,
            "has spaces",
            "under review",
            "special!chars",
        ],
    )
    # Aliases: broad charset, only '/' and ':' disallowed
    tsi.ObjSetAliasReq(
        project_id="test/proj",
        object_id="obj",
        digest="abc123",
        alias="production",
    )
    tsi.ObjSetAliasReq(
        project_id="test/proj",
        object_id="obj",
        digest="abc123",
        alias="my-deploy.v2",
    )
    tsi.ObjSetAliasReq(
        project_id="test/proj",
        object_id="obj",
        digest="abc123",
        alias="has spaces",
    )


def test_alias_invalid_characters():
    """Aliases cannot contain '/' or ':'."""
    with pytest.raises(ValidationError):
        tsi.ObjSetAliasReq(
            project_id="test/proj",
            object_id="obj",
            digest="abc123",
            alias="path/slash",
        )
    with pytest.raises(ValidationError):
        tsi.ObjSetAliasReq(
            project_id="test/proj",
            object_id="obj",
            digest="abc123",
            alias="has:colon",
        )


def test_tag_version_like_accepted():
    """Version-like names (v0, v1, ...) are accepted for tags (only reserved for aliases)."""
    tsi.ObjAddTagsReq(
        project_id="test/proj",
        object_id="obj",
        digest="abc123",
        tags=["v0"],
    )
    tsi.ObjAddTagsReq(
        project_id="test/proj",
        object_id="obj",
        digest="abc123",
        tags=["v999"],
    )


# --- digest_is_content_hash ---


@pytest.mark.parametrize(
    ("digest", "expected"),
    [
        # Weave base64url digest (43 alphanumeric chars)
        ("oioZ7zgsCq4K7tfFQZRubx3ZGPXmFyaeoeWHHd8KUl8", True),
        # Hex SHA-256 (64 hex chars)
        ("a" * 64, True),
        ("abcdef1234567890" * 4, True),
        # Alias names — not content hashes
        ("production", False),
        ("staging", False),
        ("my-alias", False),
        # Version-like — not content hashes (shorter than 43)
        ("v0", False),
        ("v123", False),
        # Edge cases
        ("", False),
        ("a" * 42, False),
        ("a" * 44, False),
        ("a" * 63, False),
        ("a" * 65, False),
        # 64 chars but not hex
        ("g" * 64, False),
    ],
)
def test_digest_is_content_hash(digest: str, expected: bool):
    assert digest_is_content_hash(digest) == expected
