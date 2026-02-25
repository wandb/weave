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
    assert res.objs[0].tags == ["reviewed", "staging"]


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
    """Tags must match TAG_REGEX: alphanumeric, hyphens, underscores, single spaces between words."""
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

    # Whitespace-only rejected
    with pytest.raises(ValidationError):
        tsi.ObjAddTagsReq(
            project_id="test/proj",
            object_id="obj",
            digest="abc123",
            tags=["   "],
        )

    # Special characters rejected (dots, bangs, etc.)
    for bad_tag in ["special!chars", "my.tag", "hello@world", "a+b"]:
        with pytest.raises(ValidationError):
            tsi.ObjAddTagsReq(
                project_id="test/proj",
                object_id="obj",
                digest="abc123",
                tags=[bad_tag],
            )

    # Leading/trailing spaces rejected
    with pytest.raises(ValidationError):
        tsi.ObjAddTagsReq(
            project_id="test/proj",
            object_id="obj",
            digest="abc123",
            tags=[" leading"],
        )
    with pytest.raises(ValidationError):
        tsi.ObjAddTagsReq(
            project_id="test/proj",
            object_id="obj",
            digest="abc123",
            tags=["trailing "],
        )

    # Consecutive spaces rejected
    with pytest.raises(ValidationError):
        tsi.ObjAddTagsReq(
            project_id="test/proj",
            object_id="obj",
            digest="abc123",
            tags=["two  spaces"],
        )

    # Valid tags with single spaces between words
    tsi.ObjAddTagsReq(
        project_id="test/proj",
        object_id="obj",
        digest="abc123",
        tags=["has spaces", "under review"],
    )


# --- Virtual "latest" alias ---


def test_latest_virtual_alias(client: WeaveClient):
    """The latest version should have 'latest' in its aliases; earlier versions should not."""
    weave.publish({"v": 0}, name="virtual_latest_obj")
    weave.publish({"v": 1}, name="virtual_latest_obj")

    res = client.server.objs_query(
        tsi.ObjQueryReq(
            project_id=client._project_id(),
            filter=tsi.ObjectVersionFilter(object_ids=["virtual_latest_obj"]),
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


def test_objs_query_filter_by_alias_returns_only_aliased_version(client: WeaveClient):
    """Filtering by alias should return only the specific version the alias points to,
    not all versions of the object.
    """
    weave.publish({"v": 0}, name="alias_version_filter")
    weave.publish({"v": 1}, name="alias_version_filter")
    weave.publish({"v": 2}, name="alias_version_filter")

    res = client.server.objs_query(
        tsi.ObjQueryReq(
            project_id=client._project_id(),
            filter=tsi.ObjectVersionFilter(object_ids=["alias_version_filter"]),
            sort_by=[tsi.SortBy(field="created_at", direction="asc")],
        )
    )
    assert len(res.objs) == 3
    v1 = res.objs[1]  # middle version

    # Alias only v1
    client.server.obj_set_alias(
        tsi.ObjSetAliasReq(
            project_id=client._project_id(),
            object_id=v1.object_id,
            digest=v1.digest,
            alias="pinned",
        )
    )

    # Filter by alias — should return only v1, not all 3 versions
    filtered = client.server.objs_query(
        tsi.ObjQueryReq(
            project_id=client._project_id(),
            filter=tsi.ObjectVersionFilter(aliases=["pinned"]),
        )
    )
    assert len(filtered.objs) == 1
    assert filtered.objs[0].digest == v1.digest
    assert filtered.objs[0].version_index == 1


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


def test_obj_read_enrichment_multi_version(client: WeaveClient):
    """obj_read on latest version returns 'latest' alias; older version does not."""
    weave.publish({"v": 0}, name="read_enrich_multi")
    weave.publish({"v": 1}, name="read_enrich_multi")

    # Get both versions
    res = client.server.objs_query(
        tsi.ObjQueryReq(
            project_id=client._project_id(),
            filter=tsi.ObjectVersionFilter(object_ids=["read_enrich_multi"]),
            sort_by=[tsi.SortBy(field="created_at", direction="asc")],
        )
    )
    v0, v1 = res.objs[0], res.objs[1]

    # Add a real alias to v0
    client.server.obj_set_alias(
        tsi.ObjSetAliasReq(
            project_id=client._project_id(),
            object_id=v0.object_id,
            digest=v0.digest,
            alias="stable",
        )
    )

    # obj_read on older version: has real alias, but NOT "latest"
    read_v0 = client.server.obj_read(
        tsi.ObjReadReq(
            project_id=client._project_id(),
            object_id=v0.object_id,
            digest=v0.digest,
            include_tags_and_aliases=True,
        )
    )
    assert "stable" in read_v0.obj.aliases
    assert "latest" not in read_v0.obj.aliases

    # obj_read on latest version: has "latest"
    read_v1 = client.server.obj_read(
        tsi.ObjReadReq(
            project_id=client._project_id(),
            object_id=v1.object_id,
            digest=v1.digest,
            include_tags_and_aliases=True,
        )
    )
    assert "latest" in read_v1.obj.aliases


def test_obj_read_enrichment_no_tags_or_aliases(client: WeaveClient):
    """obj_read with enrichment on an object with no tags/aliases returns empty lists."""
    object_id, digest = _publish_obj(client, "read_enrich_empty")

    res = client.server.obj_read(
        tsi.ObjReadReq(
            project_id=client._project_id(),
            object_id=object_id,
            digest=digest,
            include_tags_and_aliases=True,
        )
    )
    assert res.obj.tags == []
    assert "latest" in res.obj.aliases  # still the latest version
    # No other aliases besides "latest"
    assert res.obj.aliases == ["latest"]


def test_obj_read_by_latest_digest_with_enrichment(client: WeaveClient):
    """obj_read with digest='latest' returns enriched tags/aliases."""
    weave.publish({"v": 0}, name="read_latest_digest")
    weave.publish({"v": 1}, name="read_latest_digest")

    # Tag v1 (the latest)
    res = client.server.objs_query(
        tsi.ObjQueryReq(
            project_id=client._project_id(),
            filter=tsi.ObjectVersionFilter(
                object_ids=["read_latest_digest"],
                latest_only=True,
            ),
        )
    )
    v1 = res.objs[0]
    client.server.obj_add_tags(
        tsi.ObjAddTagsReq(
            project_id=client._project_id(),
            object_id=v1.object_id,
            digest=v1.digest,
            tags=["deployed"],
        )
    )

    # Read using digest="latest"
    read_res = client.server.obj_read(
        tsi.ObjReadReq(
            project_id=client._project_id(),
            object_id="read_latest_digest",
            digest="latest",
            include_tags_and_aliases=True,
        )
    )
    assert read_res.obj.version_index == 1
    assert read_res.obj.tags == ["deployed"]
    assert "latest" in read_res.obj.aliases


def test_obj_read_by_alias_enrichment(client: WeaveClient):
    """obj_read via alias resolution includes all aliases and the virtual 'latest'."""
    object_id, digest = _publish_obj(client, "read_alias_enrich")

    client.server.obj_set_alias(
        tsi.ObjSetAliasReq(
            project_id=client._project_id(),
            object_id=object_id,
            digest=digest,
            alias="production",
        )
    )
    client.server.obj_set_alias(
        tsi.ObjSetAliasReq(
            project_id=client._project_id(),
            object_id=object_id,
            digest=digest,
            alias="stable",
        )
    )

    # Read by alias name
    res = client.server.obj_read(
        tsi.ObjReadReq(
            project_id=client._project_id(),
            object_id=object_id,
            digest="production",
            include_tags_and_aliases=True,
        )
    )
    assert "production" in res.obj.aliases
    assert "stable" in res.obj.aliases
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


# --- SDK client methods (WeaveClient.add_tags, remove_tags, set_alias, remove_alias) ---


def test_sdk_add_tags(client: WeaveClient):
    ref = weave.publish({"data": "test"}, name="sdk_add_tags_obj")

    client.add_tags(ref, ["alpha", "beta"])

    res = client.server.objs_query(
        tsi.ObjQueryReq(
            project_id=client._project_id(),
            filter=tsi.ObjectVersionFilter(object_ids=[ref.name]),
            include_tags_and_aliases=True,
        )
    )
    assert sorted(res.objs[0].tags) == ["alpha", "beta"]


def test_sdk_remove_tags(client: WeaveClient):
    ref = weave.publish({"data": "test"}, name="sdk_rm_tags_obj")

    client.add_tags(ref, ["x", "y"])
    client.remove_tags(ref, ["x"])

    res = client.server.objs_query(
        tsi.ObjQueryReq(
            project_id=client._project_id(),
            filter=tsi.ObjectVersionFilter(object_ids=[ref.name]),
            include_tags_and_aliases=True,
        )
    )
    assert res.objs[0].tags == ["y"]


def test_sdk_set_alias(client: WeaveClient):
    ref = weave.publish({"data": "test"}, name="sdk_set_alias_obj")

    client.set_alias(ref, "production")

    res = client.server.objs_query(
        tsi.ObjQueryReq(
            project_id=client._project_id(),
            filter=tsi.ObjectVersionFilter(object_ids=[ref.name]),
            include_tags_and_aliases=True,
        )
    )
    assert "production" in res.objs[0].aliases


def test_sdk_remove_alias(client: WeaveClient):
    ref = weave.publish({"data": "test"}, name="sdk_rm_alias_obj")

    client.set_alias(ref, "staging")
    client.remove_alias(ref.name, "staging")

    res = client.server.objs_query(
        tsi.ObjQueryReq(
            project_id=client._project_id(),
            filter=tsi.ObjectVersionFilter(object_ids=[ref.name]),
            include_tags_and_aliases=True,
        )
    )
    assert "staging" not in (res.objs[0].aliases or [])


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
    """Tags match TAG_REGEX; aliases disallow only '/' and ':'."""
    # Tags: alphanumeric, hyphens, underscores, single spaces between words
    tsi.ObjAddTagsReq(
        project_id="test/proj",
        object_id="obj",
        digest="abc123",
        tags=[
            "reviewed",
            "my-tag",
            "my_tag",
            "Tag123",
            "a" * 256,
            "has spaces",
            "under review",
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


def test_alias_whitespace_only():
    """Whitespace-only alias names should be rejected."""
    with pytest.raises(ValidationError):
        tsi.ObjSetAliasReq(
            project_id="test/proj",
            object_id="obj",
            digest="abc123",
            alias="   ",
        )
    with pytest.raises(ValidationError):
        tsi.ObjSetAliasReq(
            project_id="test/proj",
            object_id="obj",
            digest="abc123",
            alias="\t",
        )


def test_tag_deduplication():
    """Duplicate tags in a single request should be deduplicated."""
    req = tsi.ObjAddTagsReq(
        project_id="test/proj",
        object_id="obj",
        digest="abc123",
        tags=["a", "b", "a"],
    )
    assert req.tags == ["a", "b"]


# --- List endpoints ---


def test_tags_list_empty_project(client: WeaveClient):
    """Empty project returns empty list."""
    res = client.server.tags_list(tsi.TagsListReq(project_id=client._project_id()))
    assert res.tags == []


def test_tags_list_returns_distinct(client: WeaveClient):
    """Multiple objects with overlapping tags returns deduplicated sorted list."""
    oid1, d1 = _publish_obj(client, "tl_obj1")
    oid2, d2 = _publish_obj(client, "tl_obj2")

    client.server.obj_add_tags(
        tsi.ObjAddTagsReq(
            project_id=client._project_id(),
            object_id=oid1,
            digest=d1,
            tags=["beta", "alpha"],
        )
    )
    client.server.obj_add_tags(
        tsi.ObjAddTagsReq(
            project_id=client._project_id(),
            object_id=oid2,
            digest=d2,
            tags=["alpha", "gamma"],
        )
    )

    res = client.server.tags_list(tsi.TagsListReq(project_id=client._project_id()))
    assert res.tags == ["alpha", "beta", "gamma"]


def test_tags_list_excludes_removed(client: WeaveClient):
    """Removed tags don't appear in the list."""
    oid, d = _publish_obj(client, "tl_rm_obj")

    client.server.obj_add_tags(
        tsi.ObjAddTagsReq(
            project_id=client._project_id(),
            object_id=oid,
            digest=d,
            tags=["keep", "remove-me"],
        )
    )
    client.server.obj_remove_tags(
        tsi.ObjRemoveTagsReq(
            project_id=client._project_id(),
            object_id=oid,
            digest=d,
            tags=["remove-me"],
        )
    )

    res = client.server.tags_list(tsi.TagsListReq(project_id=client._project_id()))
    assert res.tags == ["keep"]


def test_aliases_list_empty_project(client: WeaveClient):
    """Empty project returns empty list."""
    res = client.server.aliases_list(
        tsi.AliasesListReq(project_id=client._project_id())
    )
    assert res.aliases == []


def test_aliases_list_returns_distinct(client: WeaveClient):
    """Returns deduplicated sorted aliases."""
    oid1, d1 = _publish_obj(client, "al_obj1")
    oid2, d2 = _publish_obj(client, "al_obj2")

    client.server.obj_set_alias(
        tsi.ObjSetAliasReq(
            project_id=client._project_id(),
            object_id=oid1,
            digest=d1,
            alias="production",
        )
    )
    client.server.obj_set_alias(
        tsi.ObjSetAliasReq(
            project_id=client._project_id(),
            object_id=oid2,
            digest=d2,
            alias="canary",
        )
    )

    res = client.server.aliases_list(
        tsi.AliasesListReq(project_id=client._project_id())
    )
    assert res.aliases == ["canary", "production"]


def test_aliases_list_excludes_removed(client: WeaveClient):
    """Removed aliases don't appear in the list."""
    oid, d = _publish_obj(client, "al_rm_obj")

    client.server.obj_set_alias(
        tsi.ObjSetAliasReq(
            project_id=client._project_id(),
            object_id=oid,
            digest=d,
            alias="keep-alias",
        )
    )
    client.server.obj_set_alias(
        tsi.ObjSetAliasReq(
            project_id=client._project_id(),
            object_id=oid,
            digest=d,
            alias="remove-alias",
        )
    )
    client.server.obj_remove_alias(
        tsi.ObjRemoveAliasReq(
            project_id=client._project_id(),
            object_id=oid,
            alias="remove-alias",
        )
    )

    res = client.server.aliases_list(
        tsi.AliasesListReq(project_id=client._project_id())
    )
    assert res.aliases == ["keep-alias"]


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


# --- Additional query filtering tests ---


def test_filter_by_latest_alias(client: WeaveClient):
    """Filtering by alias=['latest'] should return only the latest version of each object."""
    weave.publish({"v": 0}, name="filter_by_latest_alias_obj")
    weave.publish({"v": 1}, name="filter_by_latest_alias_obj")

    res = client.server.objs_query(
        tsi.ObjQueryReq(
            project_id=client._project_id(),
            filter=tsi.ObjectVersionFilter(
                object_ids=["filter_by_latest_alias_obj"],
                aliases=["latest"],
            ),
            include_tags_and_aliases=True,
        )
    )
    assert len(res.objs) == 1
    assert "latest" in res.objs[0].aliases


def test_filter_by_nonexistent_alias(client: WeaveClient):
    """Filtering by a non-existent alias should return an empty result, not an error."""
    _publish_obj(client, "filter_noalias_obj")

    res = client.server.objs_query(
        tsi.ObjQueryReq(
            project_id=client._project_id(),
            filter=tsi.ObjectVersionFilter(aliases=["does-not-exist"]),
        )
    )
    assert len(res.objs) == 0


def test_filter_by_nonexistent_tag(client: WeaveClient):
    """Filtering by a non-existent tag should return an empty result, not an error."""
    _publish_obj(client, "filter_notag_obj")

    res = client.server.objs_query(
        tsi.ObjQueryReq(
            project_id=client._project_id(),
            filter=tsi.ObjectVersionFilter(tags=["does-not-exist"]),
        )
    )
    assert len(res.objs) == 0


def test_filter_by_multiple_tags(client: WeaveClient):
    """Filtering by multiple tags should return objects matching any of the tags."""
    oid1, d1 = _publish_obj(client, "multi_tag_a")
    oid2, d2 = _publish_obj(client, "multi_tag_b")
    _publish_obj(client, "multi_tag_c")  # no tags

    client.server.obj_add_tags(
        tsi.ObjAddTagsReq(
            project_id=client._project_id(),
            object_id=oid1,
            digest=d1,
            tags=["alpha"],
        )
    )
    client.server.obj_add_tags(
        tsi.ObjAddTagsReq(
            project_id=client._project_id(),
            object_id=oid2,
            digest=d2,
            tags=["beta"],
        )
    )

    res = client.server.objs_query(
        tsi.ObjQueryReq(
            project_id=client._project_id(),
            filter=tsi.ObjectVersionFilter(tags=["alpha", "beta"]),
        )
    )
    returned_ids = {o.object_id for o in res.objs}
    assert returned_ids == {"multi_tag_a", "multi_tag_b"}


def test_filter_by_empty_tags_list(client: WeaveClient):
    """Filtering with an empty tags list should not filter (return all objects)."""
    _publish_obj(client, "empty_tags_obj")

    # Empty tags list — should behave as no filter
    res = client.server.objs_query(
        tsi.ObjQueryReq(
            project_id=client._project_id(),
            filter=tsi.ObjectVersionFilter(
                object_ids=["empty_tags_obj"],
                tags=[],
            ),
        )
    )
    assert len(res.objs) >= 1


def test_tags_on_deleted_object(client: WeaveClient):
    """Adding tags to a deleted object should fail with NotFoundError."""
    object_id, digest = _publish_obj(client, "deleted_tag_obj")

    # Delete the object
    client.server.obj_delete(
        tsi.ObjDeleteReq(
            project_id=client._project_id(),
            object_id=object_id,
            digests=[digest],
        )
    )

    # Attempting to add tags to the deleted object should fail
    with pytest.raises(NotFoundError):
        client.server.obj_add_tags(
            tsi.ObjAddTagsReq(
                project_id=client._project_id(),
                object_id=object_id,
                digest=digest,
                tags=["should-fail"],
            )
        )


def test_alias_on_deleted_object(client: WeaveClient):
    """Setting an alias on a deleted object should fail with NotFoundError."""
    object_id, digest = _publish_obj(client, "deleted_alias_obj")

    client.server.obj_delete(
        tsi.ObjDeleteReq(
            project_id=client._project_id(),
            object_id=object_id,
            digests=[digest],
        )
    )

    with pytest.raises(NotFoundError):
        client.server.obj_set_alias(
            tsi.ObjSetAliasReq(
                project_id=client._project_id(),
                object_id=object_id,
                digest=digest,
                alias="should-fail",
            )
        )


def test_cross_object_digest_isolation(client: WeaveClient):
    """Tags/aliases on object A should not leak to object B even if digests overlap."""
    oid_a, digest_a = _publish_obj(client, "cross_obj_a")
    oid_b, digest_b = _publish_obj(client, "cross_obj_b")

    # Tag only object A
    client.server.obj_add_tags(
        tsi.ObjAddTagsReq(
            project_id=client._project_id(),
            object_id=oid_a,
            digest=digest_a,
            tags=["only-on-a"],
        )
    )
    # Alias only object B
    client.server.obj_set_alias(
        tsi.ObjSetAliasReq(
            project_id=client._project_id(),
            object_id=oid_b,
            digest=digest_b,
            alias="only-on-b",
        )
    )

    res = client.server.objs_query(
        tsi.ObjQueryReq(
            project_id=client._project_id(),
            filter=tsi.ObjectVersionFilter(object_ids=[oid_a, oid_b]),
            include_tags_and_aliases=True,
        )
    )
    objs_by_id = {o.object_id: o for o in res.objs}

    assert "only-on-a" in objs_by_id[oid_a].tags
    assert "only-on-a" not in objs_by_id[oid_b].tags

    assert "only-on-b" in objs_by_id[oid_b].aliases
    assert "only-on-b" not in (objs_by_id[oid_a].aliases or [])


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
