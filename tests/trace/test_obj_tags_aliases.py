import pytest
from pydantic import ValidationError

import weave
from weave.trace.refs import ObjectRef
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


def test_readd_tag_after_removal(client: WeaveClient):
    """Removing a tag and re-adding it should make it appear again."""
    object_id, digest = _publish_obj(client, "readd_tag_obj")

    client.server.obj_add_tags(
        tsi.ObjAddTagsReq(
            project_id=client._project_id(),
            object_id=object_id,
            digest=digest,
            tags=["ephemeral"],
        )
    )
    client.server.obj_remove_tags(
        tsi.ObjRemoveTagsReq(
            project_id=client._project_id(),
            object_id=object_id,
            digest=digest,
            tags=["ephemeral"],
        )
    )
    # Re-add the same tag
    client.server.obj_add_tags(
        tsi.ObjAddTagsReq(
            project_id=client._project_id(),
            object_id=object_id,
            digest=digest,
            tags=["ephemeral"],
        )
    )

    res = client.server.objs_query(
        tsi.ObjQueryReq(
            project_id=client._project_id(),
            filter=tsi.ObjectVersionFilter(object_ids=[object_id]),
            include_tags_and_aliases=True,
        )
    )
    assert res.objs[0].tags == ["ephemeral"]


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


def test_set_aliases(client: WeaveClient):
    object_id, digest = _publish_obj(client, "alias_obj")

    client.server.obj_set_aliases(
        tsi.ObjSetAliasesReq(
            project_id=client._project_id(),
            object_id=object_id,
            digest=digest,
            aliases=["production"],
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


def test_set_aliases_reassignment(client: WeaveClient):
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
    client.server.obj_set_aliases(
        tsi.ObjSetAliasesReq(
            project_id=client._project_id(),
            object_id=v0.object_id,
            digest=v0.digest,
            aliases=["staging"],
        )
    )

    # Move alias to v1
    client.server.obj_set_aliases(
        tsi.ObjSetAliasesReq(
            project_id=client._project_id(),
            object_id=v1.object_id,
            digest=v1.digest,
            aliases=["staging"],
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

    client.server.obj_set_aliases(
        tsi.ObjSetAliasesReq(
            project_id=client._project_id(),
            object_id=object_id,
            digest=digest,
            aliases=["temp-alias"],
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
        tsi.ObjSetAliasesReq(
            project_id="test/proj",
            object_id="obj",
            digest="abc123",
            aliases=["latest"],
        )

    with pytest.raises(ValidationError):
        tsi.ObjSetAliasesReq(
            project_id="test/proj",
            object_id="obj",
            digest="abc123",
            aliases=["v0"],
        )

    with pytest.raises(ValidationError):
        tsi.ObjSetAliasesReq(
            project_id="test/proj",
            object_id="obj",
            digest="abc123",
            aliases=["v123"],
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

    client.server.obj_set_aliases(
        tsi.ObjSetAliasesReq(
            project_id=client._project_id(),
            object_id=object_id,
            digest=digest,
            aliases=["production"],
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
    client.server.obj_set_aliases(
        tsi.ObjSetAliasesReq(
            project_id=client._project_id(),
            object_id=v1.object_id,
            digest=v1.digest,
            aliases=["pinned"],
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

    client.server.obj_set_aliases(
        tsi.ObjSetAliasesReq(
            project_id=client._project_id(),
            object_id=object_id,
            digest=digest,
            aliases=["production"],
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
        client.server.obj_set_aliases(
            tsi.ObjSetAliasesReq(
                project_id=client._project_id(),
                object_id="nonexistent_object",
                digest="0000000000000000000000000000000000000000000000000000000000000000",
                aliases=["prod"],
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
    client.server.obj_set_aliases(
        tsi.ObjSetAliasesReq(
            project_id=client._project_id(),
            object_id=object_id,
            digest=digest,
            aliases=["prod"],
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
    client.server.obj_set_aliases(
        tsi.ObjSetAliasesReq(
            project_id=client._project_id(),
            object_id=v0.object_id,
            digest=v0.digest,
            aliases=["stable"],
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

    client.server.obj_set_aliases(
        tsi.ObjSetAliasesReq(
            project_id=client._project_id(),
            object_id=object_id,
            digest=digest,
            aliases=["production"],
        )
    )
    client.server.obj_set_aliases(
        tsi.ObjSetAliasesReq(
            project_id=client._project_id(),
            object_id=object_id,
            digest=digest,
            aliases=["stable"],
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

    client.server.obj_set_aliases(
        tsi.ObjSetAliasesReq(
            project_id=client._project_id(),
            object_id=v0.object_id,
            digest=v0.digest,
            aliases=["stable"],
        )
    )
    client.server.obj_set_aliases(
        tsi.ObjSetAliasesReq(
            project_id=client._project_id(),
            object_id=v1.object_id,
            digest=v1.digest,
            aliases=["canary"],
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


# --- SDK client methods (WeaveClient.add_tags, remove_tags, set_aliases, remove_alias) ---


def test_sdk_add_tags(client: WeaveClient):
    ref = weave.publish({"data": "test"}, name="sdk_add_tags_obj")

    client.add_tags(ref, ["alpha", "beta"])

    assert client.get_tags(ref) == ["alpha", "beta"]


def test_sdk_remove_tags(client: WeaveClient):
    ref = weave.publish({"data": "test"}, name="sdk_rm_tags_obj")

    client.add_tags(ref, ["x", "y"])
    client.remove_tags(ref, ["x"])

    assert client.get_tags(ref) == ["y"]


def test_sdk_get_tags(client: WeaveClient):
    ref = weave.publish({"data": "test"}, name="sdk_get_tags_obj")

    assert client.get_tags(ref) == []

    client.add_tags(ref, ["tag1", "tag2"])
    assert client.get_tags(ref) == ["tag1", "tag2"]


def test_sdk_set_aliases(client: WeaveClient):
    ref = weave.publish({"data": "test"}, name="sdk_set_alias_obj")

    client.set_aliases(ref, "production")

    assert "production" in client.get_aliases(ref)


def test_sdk_remove_alias(client: WeaveClient):
    ref = weave.publish({"data": "test"}, name="sdk_rm_alias_obj")

    client.set_aliases(ref, "staging")
    client.remove_alias(ref, "staging")

    assert "staging" not in client.get_aliases(ref)


def test_sdk_get_aliases(client: WeaveClient):
    ref = weave.publish({"data": "test"}, name="sdk_get_aliases_obj")

    # Every latest version has a virtual "latest" alias
    aliases = client.get_aliases(ref)
    assert "latest" in aliases

    client.set_aliases(ref, "canary")
    aliases = client.get_aliases(ref)
    assert "canary" in aliases
    assert "latest" in aliases


def test_sdk_add_tags_idempotent(client: WeaveClient):
    """Adding the same tag multiple times should not create duplicates."""
    ref = weave.publish({"data": "test"}, name="sdk_idem_tags_obj")

    client.add_tags(ref, ["dup"])
    client.add_tags(ref, ["dup"])
    client.add_tags(ref, ["dup"])

    assert client.get_tags(ref) == ["dup"]


def test_sdk_remove_nonexistent_tag(client: WeaveClient):
    """Removing a tag that was never added should succeed silently."""
    ref = weave.publish({"data": "test"}, name="sdk_rm_noexist_tag")

    client.remove_tags(ref, ["never-added"])

    assert client.get_tags(ref) == []


def test_sdk_readd_tag_after_removal(client: WeaveClient):
    """Removing then re-adding a tag should make it appear again."""
    ref = weave.publish({"data": "test"}, name="sdk_readd_tag_obj")

    client.add_tags(ref, ["ephemeral"])
    client.remove_tags(ref, ["ephemeral"])
    assert client.get_tags(ref) == []

    client.add_tags(ref, ["ephemeral"])
    assert client.get_tags(ref) == ["ephemeral"]


def test_sdk_tags_scoped_to_version(client: WeaveClient):
    """Tags on v0 should not appear on v1."""
    ref_v0 = weave.publish({"v": 0}, name="sdk_tag_scope_obj")
    ref_v1 = weave.publish({"v": 1}, name="sdk_tag_scope_obj")

    client.add_tags(ref_v0, ["v0-only"])

    assert "v0-only" in client.get_tags(ref_v0)
    assert client.get_tags(ref_v1) == []


def test_sdk_alias_reassignment(client: WeaveClient):
    """Setting an alias on v1 should move it away from v0."""
    ref_v0 = weave.publish({"v": 0}, name="sdk_alias_reassign")
    ref_v1 = weave.publish({"v": 1}, name="sdk_alias_reassign")

    client.set_aliases(ref_v0, "staging")
    assert "staging" in client.get_aliases(ref_v0)

    # Move alias to v1
    client.set_aliases(ref_v1, "staging")
    assert "staging" not in client.get_aliases(ref_v0)
    assert "staging" in client.get_aliases(ref_v1)


def test_sdk_remove_nonexistent_alias(client: WeaveClient):
    """Removing an alias that was never set should succeed silently."""
    ref = weave.publish({"data": "test"}, name="sdk_rm_noexist_alias")

    client.remove_alias(ref, "never-set")


def test_sdk_multiple_tags_and_aliases(client: WeaveClient):
    """An object version can have multiple tags and aliases simultaneously."""
    ref = weave.publish({"data": "test"}, name="sdk_multi_obj")

    client.add_tags(ref, ["reviewed", "production", "v2"])
    client.set_aliases(ref, "prod")
    client.set_aliases(ref, "stable")

    tags = client.get_tags(ref)
    assert tags == ["production", "reviewed", "v2"]

    aliases = client.get_aliases(ref)
    assert "prod" in aliases
    assert "stable" in aliases
    assert "latest" in aliases


def test_sdk_add_tags_error_nonexistent_object(client: WeaveClient):
    """Adding tags to a non-existent object should raise NotFoundError."""
    fake_ref = ObjectRef(
        entity="test",
        project="test",
        name="nonexistent_object",
        _digest="0000000000000000000000000000000000000000000",
    )
    with pytest.raises(NotFoundError):
        client.add_tags(fake_ref, ["tag"])


def test_sdk_set_aliases_error_nonexistent_object(client: WeaveClient):
    """Setting an alias on a non-existent object should raise NotFoundError."""
    fake_ref = ObjectRef(
        entity="test",
        project="test",
        name="nonexistent_object",
        _digest="0000000000000000000000000000000000000000000",
    )
    with pytest.raises(NotFoundError):
        client.set_aliases(fake_ref, "prod")


def test_sdk_list_tags_excludes_removed(client: WeaveClient):
    """list_tags should not include tags that have been removed."""
    ref = weave.publish({"data": "test"}, name="sdk_list_tags_rm_obj")

    client.add_tags(ref, ["keep", "remove-me"])
    client.remove_tags(ref, ["remove-me"])

    tags = client.list_tags()
    assert "keep" in tags
    assert "remove-me" not in tags


def test_sdk_list_aliases_excludes_removed(client: WeaveClient):
    """list_aliases should not include aliases that have been removed."""
    ref = weave.publish({"data": "test"}, name="sdk_list_aliases_rm_obj")

    client.set_aliases(ref, "keep-alias")
    client.set_aliases(ref, "remove-alias")
    client.remove_alias(ref, "remove-alias")

    aliases = client.list_aliases()
    assert "keep-alias" in aliases
    assert "remove-alias" not in aliases


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
    tsi.ObjSetAliasesReq(
        project_id="test/proj",
        object_id="obj",
        digest="abc123",
        aliases=["production"],
    )
    tsi.ObjSetAliasesReq(
        project_id="test/proj",
        object_id="obj",
        digest="abc123",
        aliases=["my-deploy.v2"],
    )
    tsi.ObjSetAliasesReq(
        project_id="test/proj",
        object_id="obj",
        digest="abc123",
        aliases=["has spaces"],
    )


def test_alias_invalid_characters():
    """Aliases cannot contain '/' or ':'."""
    with pytest.raises(ValidationError):
        tsi.ObjSetAliasesReq(
            project_id="test/proj",
            object_id="obj",
            digest="abc123",
            aliases=["path/slash"],
        )
    with pytest.raises(ValidationError):
        tsi.ObjSetAliasesReq(
            project_id="test/proj",
            object_id="obj",
            digest="abc123",
            aliases=["has:colon"],
        )


def test_alias_whitespace_only():
    """Whitespace-only alias names should be rejected."""
    with pytest.raises(ValidationError):
        tsi.ObjSetAliasesReq(
            project_id="test/proj",
            object_id="obj",
            digest="abc123",
            aliases=["   "],
        )
    with pytest.raises(ValidationError):
        tsi.ObjSetAliasesReq(
            project_id="test/proj",
            object_id="obj",
            digest="abc123",
            aliases=["\t"],
        )


def test_alias_empty_string():
    """Empty string alias should be rejected."""
    with pytest.raises(ValidationError):
        tsi.ObjSetAliasesReq(
            project_id="test/proj",
            object_id="obj",
            digest="abc123",
            aliases=[""],
        )


def test_alias_too_long():
    """Alias longer than 128 characters should be rejected."""
    with pytest.raises(ValidationError):
        tsi.ObjSetAliasesReq(
            project_id="test/proj",
            object_id="obj",
            digest="abc123",
            aliases=["a" * 129],
        )

    # Exactly 128 should be fine
    tsi.ObjSetAliasesReq(
        project_id="test/proj",
        object_id="obj",
        digest="abc123",
        aliases=["a" * 128],
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

    client.server.obj_set_aliases(
        tsi.ObjSetAliasesReq(
            project_id=client._project_id(),
            object_id=oid1,
            digest=d1,
            aliases=["production"],
        )
    )
    client.server.obj_set_aliases(
        tsi.ObjSetAliasesReq(
            project_id=client._project_id(),
            object_id=oid2,
            digest=d2,
            aliases=["canary"],
        )
    )

    res = client.server.aliases_list(
        tsi.AliasesListReq(project_id=client._project_id())
    )
    assert res.aliases == ["canary", "production"]


def test_aliases_list_excludes_removed(client: WeaveClient):
    """Removed aliases don't appear in the list."""
    oid, d = _publish_obj(client, "al_rm_obj")

    client.server.obj_set_aliases(
        tsi.ObjSetAliasesReq(
            project_id=client._project_id(),
            object_id=oid,
            digest=d,
            aliases=["keep-alias"],
        )
    )
    client.server.obj_set_aliases(
        tsi.ObjSetAliasesReq(
            project_id=client._project_id(),
            object_id=oid,
            digest=d,
            aliases=["remove-alias"],
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


# --- SDK list_tags / list_aliases ---


def test_sdk_list_tags(client: WeaveClient):
    ref = weave.publish({"data": "test"}, name="sdk_list_tags_obj")
    client.add_tags(ref, ["zeta", "alpha"])

    tags = client.list_tags()
    assert "alpha" in tags
    assert "zeta" in tags
    # Verify sorted order is enforced client-side
    assert tags == sorted(tags)


def test_sdk_list_aliases(client: WeaveClient):
    ref = weave.publish({"data": "test"}, name="sdk_list_aliases_obj")
    client.set_aliases(ref, "zz-alias")
    client.set_aliases(ref, "aa-alias")

    aliases = client.list_aliases()
    assert "aa-alias" in aliases
    assert "zz-alias" in aliases
    # Verify sorted order is enforced client-side
    assert aliases == sorted(aliases)


def test_tag_named_latest_allowed(client: WeaveClient):
    """'latest' is reserved for aliases but is a perfectly valid tag name."""
    object_id, digest = _publish_obj(client, "tag_latest_obj")

    client.server.obj_add_tags(
        tsi.ObjAddTagsReq(
            project_id=client._project_id(),
            object_id=object_id,
            digest=digest,
            tags=["latest"],
        )
    )

    res = client.server.objs_query(
        tsi.ObjQueryReq(
            project_id=client._project_id(),
            filter=tsi.ObjectVersionFilter(object_ids=[object_id]),
            include_tags_and_aliases=True,
        )
    )
    assert "latest" in res.objs[0].tags


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
        client.server.obj_set_aliases(
            tsi.ObjSetAliasesReq(
                project_id=client._project_id(),
                object_id=object_id,
                digest=digest,
                aliases=["should-fail"],
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
    client.server.obj_set_aliases(
        tsi.ObjSetAliasesReq(
            project_id=client._project_id(),
            object_id=oid_b,
            digest=digest_b,
            aliases=["only-on-b"],
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


# --- Additional coverage: alias resolution, combined filters, batch enrichment ---


def test_obj_read_nonexistent_alias(client: WeaveClient):
    """obj_read with a digest that looks like an alias but doesn't exist should raise NotFoundError."""
    object_id, _ = _publish_obj(client, "read_noalias_obj")

    with pytest.raises(NotFoundError):
        client.server.obj_read(
            tsi.ObjReadReq(
                project_id=client._project_id(),
                object_id=object_id,
                digest="nonexistent-alias",
            )
        )


def test_filter_combined_tags_and_aliases(client: WeaveClient):
    """Filtering with both tags and aliases simultaneously should AND the conditions."""
    oid1, d1 = _publish_obj(client, "combo_obj1")
    oid2, d2 = _publish_obj(client, "combo_obj2")
    oid3, d3 = _publish_obj(client, "combo_obj3")

    # obj1: has tag "reviewed" and alias "production"
    client.server.obj_add_tags(
        tsi.ObjAddTagsReq(
            project_id=client._project_id(),
            object_id=oid1,
            digest=d1,
            tags=["reviewed"],
        )
    )
    client.server.obj_set_aliases(
        tsi.ObjSetAliasesReq(
            project_id=client._project_id(),
            object_id=oid1,
            digest=d1,
            aliases=["production"],
        )
    )

    # obj2: has tag "reviewed" but no alias "production"
    client.server.obj_add_tags(
        tsi.ObjAddTagsReq(
            project_id=client._project_id(),
            object_id=oid2,
            digest=d2,
            tags=["reviewed"],
        )
    )

    # obj3: has alias "production" but no tag "reviewed"
    client.server.obj_set_aliases(
        tsi.ObjSetAliasesReq(
            project_id=client._project_id(),
            object_id=oid3,
            digest=d3,
            aliases=["production"],
        )
    )

    # Filter with both tag AND alias — only obj1 should match
    res = client.server.objs_query(
        tsi.ObjQueryReq(
            project_id=client._project_id(),
            filter=tsi.ObjectVersionFilter(
                tags=["reviewed"],
                aliases=["production"],
            ),
        )
    )
    assert len(res.objs) == 1
    assert res.objs[0].object_id == oid1


def test_batch_enrichment_multiple_objects(client: WeaveClient):
    """Enrich 3+ distinct objects in one objs_query call and verify each gets correct tags/aliases."""
    oid1, d1 = _publish_obj(client, "batch_enrich_a")
    oid2, d2 = _publish_obj(client, "batch_enrich_b")
    oid3, d3 = _publish_obj(client, "batch_enrich_c")

    # obj1: tags=["alpha"], alias="prod"
    client.server.obj_add_tags(
        tsi.ObjAddTagsReq(
            project_id=client._project_id(),
            object_id=oid1,
            digest=d1,
            tags=["alpha"],
        )
    )
    client.server.obj_set_aliases(
        tsi.ObjSetAliasesReq(
            project_id=client._project_id(),
            object_id=oid1,
            digest=d1,
            aliases=["prod"],
        )
    )

    # obj2: tags=["beta"], no alias
    client.server.obj_add_tags(
        tsi.ObjAddTagsReq(
            project_id=client._project_id(),
            object_id=oid2,
            digest=d2,
            tags=["beta"],
        )
    )

    # obj3: no tags, alias="canary"
    client.server.obj_set_aliases(
        tsi.ObjSetAliasesReq(
            project_id=client._project_id(),
            object_id=oid3,
            digest=d3,
            aliases=["canary"],
        )
    )

    # Query all three with enrichment
    res = client.server.objs_query(
        tsi.ObjQueryReq(
            project_id=client._project_id(),
            filter=tsi.ObjectVersionFilter(
                object_ids=[oid1, oid2, oid3],
            ),
            include_tags_and_aliases=True,
        )
    )
    objs_by_id = {o.object_id: o for o in res.objs}

    assert len(objs_by_id) == 3

    # obj1: tags=["alpha"], aliases include "prod" and "latest"
    assert objs_by_id[oid1].tags == ["alpha"]
    assert "prod" in objs_by_id[oid1].aliases
    assert "latest" in objs_by_id[oid1].aliases

    # obj2: tags=["beta"], only "latest" alias (no real alias)
    assert objs_by_id[oid2].tags == ["beta"]
    assert objs_by_id[oid2].aliases == ["latest"]

    # obj3: no tags, aliases include "canary" and "latest"
    assert objs_by_id[oid3].tags == []
    assert "canary" in objs_by_id[oid3].aliases
    assert "latest" in objs_by_id[oid3].aliases


# --- publish() with tags/aliases ---


def test_publish_with_tags(client: WeaveClient):
    ref = weave.publish({"data": "tagged"}, name="pub_tags", tags=["alpha", "beta"])
    tags = client.get_tags(ref)
    assert tags == ["alpha", "beta"]


def test_publish_with_aliases(client: WeaveClient):
    ref = weave.publish(
        {"data": "aliased"}, name="pub_aliases", aliases=["staging", "canary"]
    )
    aliases = client.get_aliases(ref)
    assert "staging" in aliases
    assert "canary" in aliases


def test_publish_with_tags_and_aliases(client: WeaveClient):
    ref = weave.publish(
        {"data": "both"},
        name="pub_both",
        tags=["reviewed"],
        aliases=["production"],
    )
    assert client.get_tags(ref) == ["reviewed"]
    assert "production" in client.get_aliases(ref)


def test_publish_tags_aliases_none_default(client: WeaveClient):
    ref = weave.publish({"data": "plain"}, name="pub_plain")
    assert client.get_tags(ref) == []
    # Only the implicit "latest" alias should be present
    aliases = client.get_aliases(ref)
    assert aliases == ["latest"]


# --- set_aliases with list ---


def test_sdk_set_aliases_with_list(client: WeaveClient):
    """set_aliases should accept a list of aliases."""
    ref = weave.publish({"data": "test"}, name="sdk_set_alias_list_obj")

    client.set_aliases(ref, ["alpha", "beta", "gamma"])

    aliases = client.get_aliases(ref)
    assert "alpha" in aliases
    assert "beta" in aliases
    assert "gamma" in aliases


def test_sdk_set_aliases_with_list_single(client: WeaveClient):
    """set_aliases with a single-element list should behave like a string."""
    ref = weave.publish({"data": "test"}, name="sdk_set_alias_list_single")

    client.set_aliases(ref, ["only-one"])

    assert "only-one" in client.get_aliases(ref)


def test_sdk_set_aliases_with_empty_list(client: WeaveClient):
    """set_aliases with an empty list should be a no-op."""
    ref = weave.publish({"data": "test"}, name="sdk_set_alias_empty_list")

    client.set_aliases(ref, [])

    # Only the implicit "latest" alias should be present
    assert client.get_aliases(ref) == ["latest"]


# --- Top-level weave.* wrapper functions ---


def test_weave_add_tags(client: WeaveClient):
    """weave.add_tags() top-level function should work."""
    ref = weave.publish({"data": "test"}, name="tl_add_tags_obj")

    weave.add_tags(ref, ["top-level-tag"])

    assert "top-level-tag" in weave.get_tags(ref)


def test_weave_remove_tags(client: WeaveClient):
    """weave.remove_tags() top-level function should work."""
    ref = weave.publish({"data": "test"}, name="tl_rm_tags_obj")

    weave.add_tags(ref, ["keep", "remove"])
    weave.remove_tags(ref, ["remove"])

    tags = weave.get_tags(ref)
    assert "keep" in tags
    assert "remove" not in tags


def test_weave_set_aliases(client: WeaveClient):
    """weave.set_aliases() top-level function should work."""
    ref = weave.publish({"data": "test"}, name="tl_set_alias_obj")

    weave.set_aliases(ref, "top-level-alias")

    assert "top-level-alias" in weave.get_aliases(ref)


def test_weave_set_aliases_list(client: WeaveClient):
    """weave.set_aliases() top-level function should accept a list."""
    ref = weave.publish({"data": "test"}, name="tl_set_alias_list_obj")

    weave.set_aliases(ref, ["alias-a", "alias-b"])

    aliases = weave.get_aliases(ref)
    assert "alias-a" in aliases
    assert "alias-b" in aliases


def test_weave_remove_alias(client: WeaveClient):
    """weave.remove_alias() top-level function should work."""
    ref = weave.publish({"data": "test"}, name="tl_rm_alias_obj")

    weave.set_aliases(ref, "ephemeral")
    weave.remove_alias(ref, "ephemeral")

    assert "ephemeral" not in weave.get_aliases(ref)


def test_weave_list_tags(client: WeaveClient):
    """weave.list_tags() top-level function should work."""
    ref = weave.publish({"data": "test"}, name="tl_list_tags_obj")

    weave.add_tags(ref, ["global-tag"])

    tags = weave.list_tags()
    assert "global-tag" in tags


def test_weave_list_aliases(client: WeaveClient):
    """weave.list_aliases() top-level function should work."""
    ref = weave.publish({"data": "test"}, name="tl_list_aliases_obj")

    weave.set_aliases(ref, "global-alias")

    aliases = weave.list_aliases()
    assert "global-alias" in aliases


# --- Resolve by alias via weave.ref() / weave.get() ---


def test_resolve_by_latest_alias(client: WeaveClient):
    """weave.ref('name:latest') should resolve to the latest version."""
    weave.publish({"v": 0}, name="resolve_latest_obj")
    weave.publish({"v": 1}, name="resolve_latest_obj")

    obj = weave.ref("resolve_latest_obj:latest").get()
    assert obj["v"] == 1


def test_resolve_by_custom_alias(client: WeaveClient):
    """weave.ref('name:production') should resolve to the aliased version."""
    ref_v0 = weave.publish({"v": 0}, name="resolve_custom_obj")
    weave.publish({"v": 1}, name="resolve_custom_obj")

    client.set_aliases(ref_v0, "production")

    obj = weave.ref("resolve_custom_obj:production").get()
    assert obj["v"] == 0


def test_resolve_by_alias_after_reassignment(client: WeaveClient):
    """After reassigning an alias, weave.ref should resolve to the new version."""
    ref_v0 = weave.publish({"v": 0}, name="resolve_reassign_obj")
    ref_v1 = weave.publish({"v": 1}, name="resolve_reassign_obj")

    client.set_aliases(ref_v0, "staging")
    assert weave.ref("resolve_reassign_obj:staging").get()["v"] == 0

    # Reassign alias to v1
    client.set_aliases(ref_v1, "staging")
    assert weave.ref("resolve_reassign_obj:staging").get()["v"] == 1


def test_resolve_by_alias_set_at_publish(client: WeaveClient):
    """Aliases set via weave.publish() should be resolvable via weave.ref()."""
    weave.publish({"v": 0}, name="resolve_pub_alias_obj")
    weave.publish({"v": 1}, name="resolve_pub_alias_obj", aliases=["stable"])
    weave.publish({"v": 2}, name="resolve_pub_alias_obj")

    obj = weave.ref("resolve_pub_alias_obj:stable").get()
    assert obj["v"] == 1


def test_resolve_implicit_latest(client: WeaveClient):
    """weave.ref('name') without version should default to latest."""
    weave.publish({"v": 0}, name="resolve_implicit_obj")
    weave.publish({"v": 1}, name="resolve_implicit_obj")

    obj = weave.ref("resolve_implicit_obj").get()
    assert obj["v"] == 1


def test_get_by_alias_string(client: WeaveClient):
    """weave.get('name:alias') should resolve and return the object."""
    ref_v0 = weave.publish({"v": 0}, name="get_alias_obj")
    weave.publish({"v": 1}, name="get_alias_obj")

    client.set_aliases(ref_v0, "pinned")

    obj = weave.get("get_alias_obj:pinned")
    assert obj["v"] == 0


def test_resolve_nonexistent_alias_raises(client: WeaveClient):
    """weave.ref('name:nonexistent').get() should raise NotFoundError."""
    weave.publish({"v": 0}, name="resolve_noexist_alias")

    with pytest.raises(NotFoundError):
        weave.ref("resolve_noexist_alias:nonexistent").get()


def test_resolve_alias_returns_correct_ref_digest(client: WeaveClient):
    """The ref returned from .get() should have the real content digest, not the alias."""
    ref_v0 = weave.publish({"v": 0}, name="resolve_digest_check")
    client.set_aliases(ref_v0, "check-me")

    obj = weave.ref("resolve_digest_check:check-me").get()
    resolved_ref = obj.ref
    assert resolved_ref.digest == ref_v0.digest
    assert resolved_ref.digest != "check-me"


def test_resolve_multiple_aliases_same_version(client: WeaveClient):
    """Multiple aliases on the same version should all resolve to it."""
    ref = weave.publish({"v": 0}, name="resolve_multi_alias")
    client.set_aliases(ref, ["alpha", "beta", "gamma"])

    for alias in ["alpha", "beta", "gamma"]:
        obj = weave.ref(f"resolve_multi_alias:{alias}").get()
        assert obj["v"] == 0


# --- Tags lifecycle and persistence ---


def test_tags_survive_ref_get_roundtrip(client: WeaveClient):
    """Tags should be queryable after resolving via weave.ref().get()."""
    ref = weave.publish({"data": "tagged"}, name="tags_roundtrip_obj")
    weave.add_tags(ref, ["important", "reviewed"])

    # Get the object via ref, then check tags on the original ref
    weave.ref("tags_roundtrip_obj:latest").get()
    assert weave.get_tags(ref) == ["important", "reviewed"]


def test_tags_independent_across_objects(client: WeaveClient):
    """Tags on one object should not affect another object."""
    ref_a = weave.publish({"obj": "a"}, name="tags_indep_a")
    ref_b = weave.publish({"obj": "b"}, name="tags_indep_b")

    weave.add_tags(ref_a, ["only-on-a"])

    assert weave.get_tags(ref_a) == ["only-on-a"]
    assert weave.get_tags(ref_b) == []


def test_tags_on_multiple_versions(client: WeaveClient):
    """Each version can have its own independent tags."""
    ref_v0 = weave.publish({"v": 0}, name="tags_multi_ver")
    ref_v1 = weave.publish({"v": 1}, name="tags_multi_ver")
    ref_v2 = weave.publish({"v": 2}, name="tags_multi_ver")

    weave.add_tags(ref_v0, ["old"])
    weave.add_tags(ref_v1, ["stable", "reviewed"])
    # v2 has no tags

    assert weave.get_tags(ref_v0) == ["old"]
    assert weave.get_tags(ref_v1) == ["reviewed", "stable"]
    assert weave.get_tags(ref_v2) == []


def test_tags_bulk_add_and_remove(client: WeaveClient):
    """Adding and removing multiple tags in one call should work."""
    ref = weave.publish({"data": "test"}, name="tags_bulk_obj")

    weave.add_tags(ref, ["a", "b", "c", "d", "e"])
    assert weave.get_tags(ref) == ["a", "b", "c", "d", "e"]

    weave.remove_tags(ref, ["b", "d"])
    assert weave.get_tags(ref) == ["a", "c", "e"]


def test_tags_add_empty_list(client: WeaveClient):
    """Adding an empty tag list should be a no-op."""
    ref = weave.publish({"data": "test"}, name="tags_empty_add")

    weave.add_tags(ref, [])
    assert weave.get_tags(ref) == []


def test_tags_remove_empty_list(client: WeaveClient):
    """Removing an empty tag list should be a no-op."""
    ref = weave.publish({"data": "test"}, name="tags_empty_rm")
    weave.add_tags(ref, ["keep"])

    weave.remove_tags(ref, [])
    assert weave.get_tags(ref) == ["keep"]


def test_tags_returned_sorted(client: WeaveClient):
    """get_tags should return tags in sorted order."""
    ref = weave.publish({"data": "test"}, name="tags_sorted_obj")

    weave.add_tags(ref, ["zulu", "alpha", "mike"])
    tags = weave.get_tags(ref)
    assert tags == sorted(tags)


def test_tags_with_publish_then_add_more(client: WeaveClient):
    """Tags from publish() and add_tags() should combine."""
    ref = weave.publish(
        {"data": "test"}, name="tags_combine_obj", tags=["from-publish"]
    )
    weave.add_tags(ref, ["from-add"])

    tags = weave.get_tags(ref)
    assert "from-publish" in tags
    assert "from-add" in tags


def test_list_tags_across_objects(client: WeaveClient):
    """list_tags should return tags from all objects in the project."""
    ref_a = weave.publish({"obj": "a"}, name="list_tags_cross_a")
    ref_b = weave.publish({"obj": "b"}, name="list_tags_cross_b")

    weave.add_tags(ref_a, ["tag-on-a"])
    weave.add_tags(ref_b, ["tag-on-b"])

    all_tags = weave.list_tags()
    assert "tag-on-a" in all_tags
    assert "tag-on-b" in all_tags


def test_list_tags_deduplicates(client: WeaveClient):
    """list_tags should return each tag only once even if on multiple objects."""
    ref_a = weave.publish({"obj": "a"}, name="list_tags_dedup_a")
    ref_b = weave.publish({"obj": "b"}, name="list_tags_dedup_b")

    weave.add_tags(ref_a, ["shared-tag"])
    weave.add_tags(ref_b, ["shared-tag"])

    all_tags = weave.list_tags()
    assert all_tags.count("shared-tag") == 1


# --- Aliases complete lifecycle ---


def test_aliases_on_multiple_versions(client: WeaveClient):
    """Different versions of the same object can have different aliases."""
    ref_v0 = weave.publish({"v": 0}, name="alias_multi_ver")
    ref_v1 = weave.publish({"v": 1}, name="alias_multi_ver")

    weave.set_aliases(ref_v0, "old-stable")
    weave.set_aliases(ref_v1, "current")

    assert "old-stable" in weave.get_aliases(ref_v0)
    assert "current" not in weave.get_aliases(ref_v0)
    assert "current" in weave.get_aliases(ref_v1)
    assert "old-stable" not in weave.get_aliases(ref_v1)


def test_aliases_independent_across_objects(client: WeaveClient):
    """Same alias name on different objects should be independent."""
    ref_a = weave.publish({"obj": "a"}, name="alias_indep_a")
    ref_b = weave.publish({"obj": "b"}, name="alias_indep_b")

    weave.set_aliases(ref_a, "prod")
    weave.set_aliases(ref_b, "prod")

    # Both should have "prod"
    assert "prod" in weave.get_aliases(ref_a)
    assert "prod" in weave.get_aliases(ref_b)

    # Removing from one shouldn't affect the other
    weave.remove_alias(ref_a, "prod")
    assert "prod" not in weave.get_aliases(ref_a)
    assert "prod" in weave.get_aliases(ref_b)


def test_alias_latest_is_virtual(client: WeaveClient):
    """'latest' alias should appear on the newest version."""
    ref_v0 = weave.publish({"v": 0}, name="alias_latest_virtual")
    assert "latest" in weave.get_aliases(ref_v0)

    ref_v1 = weave.publish({"v": 1}, name="alias_latest_virtual")
    assert "latest" in weave.get_aliases(ref_v1)


def test_list_aliases_across_objects(client: WeaveClient):
    """list_aliases should return aliases from all objects in the project."""
    ref_a = weave.publish({"obj": "a"}, name="list_alias_cross_a")
    ref_b = weave.publish({"obj": "b"}, name="list_alias_cross_b")

    weave.set_aliases(ref_a, "alias-on-a")
    weave.set_aliases(ref_b, "alias-on-b")

    all_aliases = weave.list_aliases()
    assert "alias-on-a" in all_aliases
    assert "alias-on-b" in all_aliases


def test_list_aliases_deduplicates(client: WeaveClient):
    """list_aliases returns distinct aliases even if the same name is used across objects."""
    ref_a = weave.publish({"obj": "a"}, name="list_alias_dedup_a")
    ref_b = weave.publish({"obj": "b"}, name="list_alias_dedup_b")

    weave.set_aliases(ref_a, "shared-alias")
    weave.set_aliases(ref_b, "shared-alias")

    all_aliases = weave.list_aliases()
    assert "shared-alias" in all_aliases
    assert all_aliases.count("shared-alias") == 1  # distinct


def test_remove_alias_then_resolve_raises(client: WeaveClient):
    """After removing an alias, resolving it should fail."""
    ref = weave.publish({"data": "test"}, name="rm_alias_resolve")
    client.set_aliases(ref, "temporary")

    # Resolves before removal
    assert weave.ref("rm_alias_resolve:temporary").get()["data"] == "test"

    # Remove and verify it no longer resolves
    client.remove_alias(ref, "temporary")
    with pytest.raises(NotFoundError):
        weave.ref("rm_alias_resolve:temporary").get()


# --- Combined tags + aliases end-to-end ---


def test_tags_and_aliases_full_lifecycle(client: WeaveClient):
    """Full lifecycle: publish, tag, alias, resolve, reassign, remove."""
    # Publish two versions
    ref_v0 = weave.publish({"v": 0}, name="full_lifecycle_obj")
    ref_v1 = weave.publish({"v": 1}, name="full_lifecycle_obj")

    # Tag both
    weave.add_tags(ref_v0, ["deprecated"])
    weave.add_tags(ref_v1, ["stable", "reviewed"])

    # Alias v1 as production
    weave.set_aliases(ref_v1, "production")

    # Resolve alias
    obj = weave.ref("full_lifecycle_obj:production").get()
    assert obj["v"] == 1

    # Check tags/aliases
    assert weave.get_tags(ref_v0) == ["deprecated"]
    assert weave.get_tags(ref_v1) == ["reviewed", "stable"]
    assert "production" in weave.get_aliases(ref_v1)

    # Reassign alias to v0
    weave.set_aliases(ref_v0, "production")
    obj = weave.ref("full_lifecycle_obj:production").get()
    assert obj["v"] == 0
    assert "production" not in weave.get_aliases(ref_v1)

    # Remove tags
    weave.remove_tags(ref_v0, ["deprecated"])
    assert weave.get_tags(ref_v0) == []

    # Remove alias
    weave.remove_alias(ref_v0, "production")
    with pytest.raises(NotFoundError):
        weave.ref("full_lifecycle_obj:production").get()

    # list_tags/list_aliases reflect current state
    all_tags = weave.list_tags()
    assert "deprecated" not in all_tags
    assert "stable" in all_tags
    assert "reviewed" in all_tags


def test_publish_with_tags_and_aliases_then_resolve(client: WeaveClient):
    """Tags and aliases set at publish time should work with ref resolution."""
    weave.publish({"v": 0}, name="pub_resolve_obj")
    weave.publish(
        {"v": 1},
        name="pub_resolve_obj",
        tags=["release-candidate"],
        aliases=["rc"],
    )
    weave.publish({"v": 2}, name="pub_resolve_obj")

    # Resolve the alias set at publish time
    obj = weave.ref("pub_resolve_obj:rc").get()
    assert obj["v"] == 1

    # Latest should be v2
    obj_latest = weave.ref("pub_resolve_obj:latest").get()
    assert obj_latest["v"] == 2


# --- Cross-project isolation ---


def _create_obj_in_project(server, project_id: str, name: str, val: dict | None = None):
    """Create an object directly via the server in a specific project."""
    res = server.obj_create(
        tsi.ObjCreateReq(
            obj=tsi.ObjSchemaForInsert(
                project_id=project_id,
                object_id=name,
                val=val or {"data": "test"},
            )
        )
    )
    return name, res.digest


def test_tags_do_not_leak_across_projects(client: WeaveClient):
    """Tags in project A should not be visible in project B."""
    server = client.server
    proj_a = "test-entity/proj-tags-a"
    proj_b = "test-entity/proj-tags-b"

    obj_name = "shared_obj_name"
    _, digest_a = _create_obj_in_project(server, proj_a, obj_name)
    _, digest_b = _create_obj_in_project(server, proj_b, obj_name)

    # Tag object in project A
    server.obj_add_tags(
        tsi.ObjAddTagsReq(
            project_id=proj_a,
            object_id=obj_name,
            digest=digest_a,
            tags=["proj-a-only"],
        )
    )

    # Query tags in project A — should have the tag
    res_a = server.obj_read(
        tsi.ObjReadReq(
            project_id=proj_a,
            object_id=obj_name,
            digest=digest_a,
            include_tags_and_aliases=True,
        )
    )
    assert "proj-a-only" in (res_a.obj.tags or [])

    # Query tags in project B — should NOT have the tag
    res_b = server.obj_read(
        tsi.ObjReadReq(
            project_id=proj_b,
            object_id=obj_name,
            digest=digest_b,
            include_tags_and_aliases=True,
        )
    )
    assert res_b.obj.tags is None or "proj-a-only" not in res_b.obj.tags


def test_aliases_do_not_leak_across_projects(client: WeaveClient):
    """Aliases in project A should not be visible in project B."""
    server = client.server
    proj_a = "test-entity/proj-alias-a"
    proj_b = "test-entity/proj-alias-b"

    obj_name = "shared_obj_name"
    _, digest_a = _create_obj_in_project(server, proj_a, obj_name)
    _, digest_b = _create_obj_in_project(server, proj_b, obj_name)

    # Set alias in project A
    server.obj_set_aliases(
        tsi.ObjSetAliasesReq(
            project_id=proj_a,
            object_id=obj_name,
            digest=digest_a,
            aliases=["production"],
        )
    )

    # Query aliases in project A — should have the alias
    res_a = server.obj_read(
        tsi.ObjReadReq(
            project_id=proj_a,
            object_id=obj_name,
            digest=digest_a,
            include_tags_and_aliases=True,
        )
    )
    assert "production" in (res_a.obj.aliases or [])

    # Query aliases in project B — should NOT have the alias
    res_b = server.obj_read(
        tsi.ObjReadReq(
            project_id=proj_b,
            object_id=obj_name,
            digest=digest_b,
            include_tags_and_aliases=True,
        )
    )
    assert res_b.obj.aliases is None or "production" not in res_b.obj.aliases


def test_list_tags_scoped_to_project(client: WeaveClient):
    """list_tags should only return tags from the specified project."""
    server = client.server
    proj_a = "test-entity/proj-list-tags-a"
    proj_b = "test-entity/proj-list-tags-b"

    _, digest_a = _create_obj_in_project(server, proj_a, "obj_a")
    _, digest_b = _create_obj_in_project(server, proj_b, "obj_b")

    server.obj_add_tags(
        tsi.ObjAddTagsReq(
            project_id=proj_a,
            object_id="obj_a",
            digest=digest_a,
            tags=["only-in-a"],
        )
    )
    server.obj_add_tags(
        tsi.ObjAddTagsReq(
            project_id=proj_b,
            object_id="obj_b",
            digest=digest_b,
            tags=["only-in-b"],
        )
    )

    tags_a = server.tags_list(tsi.TagsListReq(project_id=proj_a))
    tags_b = server.tags_list(tsi.TagsListReq(project_id=proj_b))

    assert "only-in-a" in tags_a.tags
    assert "only-in-b" not in tags_a.tags
    assert "only-in-b" in tags_b.tags
    assert "only-in-a" not in tags_b.tags


def test_list_aliases_scoped_to_project(client: WeaveClient):
    """list_aliases should only return aliases from the specified project."""
    server = client.server
    proj_a = "test-entity/proj-list-aliases-a"
    proj_b = "test-entity/proj-list-aliases-b"

    _, digest_a = _create_obj_in_project(server, proj_a, "obj_a")
    _, digest_b = _create_obj_in_project(server, proj_b, "obj_b")

    server.obj_set_aliases(
        tsi.ObjSetAliasesReq(
            project_id=proj_a,
            object_id="obj_a",
            digest=digest_a,
            aliases=["alias-in-a"],
        )
    )
    server.obj_set_aliases(
        tsi.ObjSetAliasesReq(
            project_id=proj_b,
            object_id="obj_b",
            digest=digest_b,
            aliases=["alias-in-b"],
        )
    )

    aliases_a = server.aliases_list(tsi.AliasesListReq(project_id=proj_a))
    aliases_b = server.aliases_list(tsi.AliasesListReq(project_id=proj_b))

    assert "alias-in-a" in aliases_a.aliases
    assert "alias-in-b" not in aliases_a.aliases
    assert "alias-in-b" in aliases_b.aliases
    assert "alias-in-a" not in aliases_b.aliases


def test_alias_resolution_scoped_to_project(client: WeaveClient):
    """Resolving an alias should only find it within the correct project."""
    server = client.server
    proj_a = "test-entity/proj-resolve-a"
    proj_b = "test-entity/proj-resolve-b"

    obj_name = "shared_name"
    _, digest_a = _create_obj_in_project(server, proj_a, obj_name, {"proj": "a"})
    _create_obj_in_project(server, proj_b, obj_name, {"proj": "b"})

    # Set alias only in project A
    server.obj_set_aliases(
        tsi.ObjSetAliasesReq(
            project_id=proj_a,
            object_id=obj_name,
            digest=digest_a,
            aliases=["prod"],
        )
    )

    # Resolve in project A — should succeed
    res_a = server.obj_read(
        tsi.ObjReadReq(
            project_id=proj_a,
            object_id=obj_name,
            digest="prod",
            include_tags_and_aliases=True,
        )
    )
    assert res_a.obj.val == {"proj": "a"}

    # Resolve in project B — should fail (alias doesn't exist there)
    with pytest.raises(NotFoundError):
        server.obj_read(
            tsi.ObjReadReq(
                project_id=proj_b,
                object_id=obj_name,
                digest="prod",
            )
        )
