import time

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
            project_id=client.project_id,
            filter=tsi.ObjectVersionFilter(object_ids=[name]),
            sort_by=[tsi.SortBy(field="created_at", direction="asc")],
        )
    )
    obj = res.objs[-1]  # latest version (sorted by created_at asc)
    return obj.object_id, obj.digest


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


# ---------------------------------------------------------------------------
# Validation (no client needed)
# ---------------------------------------------------------------------------


def test_tag_validation():
    """All tag format rules: regex, length, whitespace, deduplication, version-like names."""
    # Empty tag rejected
    with pytest.raises(ValidationError):
        tsi.ObjAddTagsReq(
            project_id="test/proj", object_id="obj", digest="abc123", tags=[""]
        )

    # Too long (>256 chars) rejected
    with pytest.raises(ValidationError):
        tsi.ObjAddTagsReq(
            project_id="test/proj", object_id="obj", digest="abc123", tags=["a" * 257]
        )

    # Whitespace-only rejected
    with pytest.raises(ValidationError):
        tsi.ObjAddTagsReq(
            project_id="test/proj", object_id="obj", digest="abc123", tags=["   "]
        )

    # Special characters rejected
    for bad_tag in ["special!chars", "my.tag", "hello@world", "a+b"]:
        with pytest.raises(ValidationError):
            tsi.ObjAddTagsReq(
                project_id="test/proj", object_id="obj", digest="abc123", tags=[bad_tag]
            )

    # Leading/trailing spaces rejected
    with pytest.raises(ValidationError):
        tsi.ObjAddTagsReq(
            project_id="test/proj", object_id="obj", digest="abc123", tags=[" leading"]
        )
    with pytest.raises(ValidationError):
        tsi.ObjAddTagsReq(
            project_id="test/proj", object_id="obj", digest="abc123", tags=["trailing "]
        )

    # Consecutive spaces rejected
    with pytest.raises(ValidationError):
        tsi.ObjAddTagsReq(
            project_id="test/proj",
            object_id="obj",
            digest="abc123",
            tags=["two  spaces"],
        )

    # Valid tags accepted: alphanumeric, hyphens, underscores, single spaces, max length
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

    # Version-like names (v0, v999) are valid for tags (only reserved for aliases)
    tsi.ObjAddTagsReq(
        project_id="test/proj", object_id="obj", digest="abc123", tags=["v0"]
    )
    tsi.ObjAddTagsReq(
        project_id="test/proj", object_id="obj", digest="abc123", tags=["v999"]
    )

    # Duplicate tags in a single request are deduplicated
    req = tsi.ObjAddTagsReq(
        project_id="test/proj", object_id="obj", digest="abc123", tags=["a", "b", "a"]
    )
    assert req.tags == ["a", "b"]


def test_alias_validation():
    """All alias format rules: reserved names, invalid chars, length, whitespace."""
    # Reserved names rejected: 'latest', version-like
    for reserved in ["latest", "v0", "v123"]:
        with pytest.raises(ValidationError):
            tsi.ObjSetAliasesReq(
                project_id="test/proj",
                object_id="obj",
                digest="abc123",
                aliases=[reserved],
            )

    # Invalid characters: '/' and ':' rejected
    for bad in ["path/slash", "has:colon"]:
        with pytest.raises(ValidationError):
            tsi.ObjSetAliasesReq(
                project_id="test/proj",
                object_id="obj",
                digest="abc123",
                aliases=[bad],
            )

    # Whitespace-only rejected (spaces, tabs)
    for ws in ["   ", "\t"]:
        with pytest.raises(ValidationError):
            tsi.ObjSetAliasesReq(
                project_id="test/proj",
                object_id="obj",
                digest="abc123",
                aliases=[ws],
            )

    # Empty string rejected
    with pytest.raises(ValidationError):
        tsi.ObjSetAliasesReq(
            project_id="test/proj", object_id="obj", digest="abc123", aliases=[""]
        )

    # Too long (>128 chars) rejected
    with pytest.raises(ValidationError):
        tsi.ObjSetAliasesReq(
            project_id="test/proj",
            object_id="obj",
            digest="abc123",
            aliases=["a" * 129],
        )

    # Exactly 128 is fine
    tsi.ObjSetAliasesReq(
        project_id="test/proj",
        object_id="obj",
        digest="abc123",
        aliases=["a" * 128],
    )

    # Valid alias names: broad charset, dots, spaces all OK
    for valid in ["production", "my-deploy.v2", "has spaces"]:
        tsi.ObjSetAliasesReq(
            project_id="test/proj",
            object_id="obj",
            digest="abc123",
            aliases=[valid],
        )


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


# ---------------------------------------------------------------------------
# Server-level tag CRUD
# ---------------------------------------------------------------------------


def test_server_tag_crud(client: WeaveClient):
    """Full tag lifecycle via server API: add, remove, re-add, idempotent, remove nonexistent."""
    object_id, digest = _publish_obj(client, "srv_tag_crud")

    # Add tags
    client.server.obj_add_tags(
        tsi.ObjAddTagsReq(
            project_id=client.project_id,
            object_id=object_id,
            digest=digest,
            tags=["reviewed", "staging"],
        )
    )
    res = client.server.objs_query(
        tsi.ObjQueryReq(
            project_id=client.project_id,
            filter=tsi.ObjectVersionFilter(object_ids=[object_id]),
            include_tags_and_aliases=True,
        )
    )
    assert res.objs[0].tags == ["reviewed", "staging"]

    # Remove one tag
    client.server.obj_remove_tags(
        tsi.ObjRemoveTagsReq(
            project_id=client.project_id,
            object_id=object_id,
            digest=digest,
            tags=["reviewed"],
        )
    )
    res = client.server.objs_query(
        tsi.ObjQueryReq(
            project_id=client.project_id,
            filter=tsi.ObjectVersionFilter(object_ids=[object_id]),
            include_tags_and_aliases=True,
        )
    )
    assert res.objs[0].tags == ["staging"]

    # Remove and re-add
    client.server.obj_remove_tags(
        tsi.ObjRemoveTagsReq(
            project_id=client.project_id,
            object_id=object_id,
            digest=digest,
            tags=["staging"],
        )
    )
    client.server.obj_add_tags(
        tsi.ObjAddTagsReq(
            project_id=client.project_id,
            object_id=object_id,
            digest=digest,
            tags=["staging"],
        )
    )
    res = client.server.objs_query(
        tsi.ObjQueryReq(
            project_id=client.project_id,
            filter=tsi.ObjectVersionFilter(object_ids=[object_id]),
            include_tags_and_aliases=True,
        )
    )
    assert res.objs[0].tags == ["staging"]

    # Idempotent add (3x)
    for _ in range(3):
        client.server.obj_add_tags(
            tsi.ObjAddTagsReq(
                project_id=client.project_id,
                object_id=object_id,
                digest=digest,
                tags=["staging"],
            )
        )
    res = client.server.objs_query(
        tsi.ObjQueryReq(
            project_id=client.project_id,
            filter=tsi.ObjectVersionFilter(object_ids=[object_id]),
            include_tags_and_aliases=True,
        )
    )
    assert res.objs[0].tags == ["staging"]

    # Remove nonexistent tag — succeeds silently
    client.server.obj_remove_tags(
        tsi.ObjRemoveTagsReq(
            project_id=client.project_id,
            object_id=object_id,
            digest=digest,
            tags=["never-added"],
        )
    )

    # "latest" is a valid tag name (only reserved for aliases)
    client.server.obj_add_tags(
        tsi.ObjAddTagsReq(
            project_id=client.project_id,
            object_id=object_id,
            digest=digest,
            tags=["latest"],
        )
    )
    res = client.server.objs_query(
        tsi.ObjQueryReq(
            project_id=client.project_id,
            filter=tsi.ObjectVersionFilter(object_ids=[object_id]),
            include_tags_and_aliases=True,
        )
    )
    assert "latest" in res.objs[0].tags


# ---------------------------------------------------------------------------
# Server-level alias CRUD
# ---------------------------------------------------------------------------


def test_server_alias_crud(client: WeaveClient):
    """Full alias lifecycle via server API: set, reassign, remove, remove nonexistent."""
    object_id, digest = _publish_obj(client, "srv_alias_crud")

    # Set alias
    client.server.obj_set_aliases(
        tsi.ObjSetAliasesReq(
            project_id=client.project_id,
            object_id=object_id,
            digest=digest,
            aliases=["production"],
        )
    )
    res = client.server.objs_query(
        tsi.ObjQueryReq(
            project_id=client.project_id,
            filter=tsi.ObjectVersionFilter(object_ids=[object_id]),
            include_tags_and_aliases=True,
        )
    )
    assert "production" in res.objs[0].aliases

    # Reassignment: create two versions, move alias from v0 to v1
    weave.publish({"v": 0}, name="srv_alias_reassign")
    weave.publish({"v": 1}, name="srv_alias_reassign")
    res = client.server.objs_query(
        tsi.ObjQueryReq(
            project_id=client.project_id,
            filter=tsi.ObjectVersionFilter(object_ids=["srv_alias_reassign"]),
            sort_by=[tsi.SortBy(field="created_at", direction="asc")],
        )
    )
    v0, v1 = res.objs[0], res.objs[1]

    client.server.obj_set_aliases(
        tsi.ObjSetAliasesReq(
            project_id=client.project_id,
            object_id=v0.object_id,
            digest=v0.digest,
            aliases=["staging"],
        )
    )
    client.server.obj_set_aliases(
        tsi.ObjSetAliasesReq(
            project_id=client.project_id,
            object_id=v1.object_id,
            digest=v1.digest,
            aliases=["staging"],
        )
    )
    res = client.server.objs_query(
        tsi.ObjQueryReq(
            project_id=client.project_id,
            filter=tsi.ObjectVersionFilter(object_ids=["srv_alias_reassign"]),
            include_tags_and_aliases=True,
            sort_by=[tsi.SortBy(field="created_at", direction="asc")],
        )
    )
    assert "staging" not in (res.objs[0].aliases or [])
    assert "staging" in res.objs[1].aliases

    # Remove alias
    client.server.obj_remove_aliases(
        tsi.ObjRemoveAliasesReq(
            project_id=client.project_id,
            object_id=object_id,
            aliases=["production"],
        )
    )
    res = client.server.objs_query(
        tsi.ObjQueryReq(
            project_id=client.project_id,
            filter=tsi.ObjectVersionFilter(object_ids=[object_id]),
            include_tags_and_aliases=True,
        )
    )
    assert "production" not in (res.objs[0].aliases or [])

    # Remove nonexistent alias — succeeds silently
    client.server.obj_remove_aliases(
        tsi.ObjRemoveAliasesReq(
            project_id=client.project_id,
            object_id=object_id,
            aliases=["no-such-alias"],
        )
    )


# ---------------------------------------------------------------------------
# Server-level errors: nonexistent and deleted objects
# ---------------------------------------------------------------------------


def test_server_tag_errors(client: WeaveClient):
    """Tags on nonexistent or deleted objects raise NotFoundError.

    Note: each error scenario needs its own test function because SQLite's
    transaction state becomes dirty after a NotFoundError.
    """
    # Nonexistent object
    with pytest.raises(NotFoundError):
        client.server.obj_add_tags(
            tsi.ObjAddTagsReq(
                project_id=client.project_id,
                object_id="nonexistent_object",
                digest="0" * 64,
                tags=["tag"],
            )
        )


def test_server_alias_errors(client: WeaveClient):
    """Aliases on nonexistent or deleted objects raise NotFoundError."""
    # Nonexistent object
    with pytest.raises(NotFoundError):
        client.server.obj_set_aliases(
            tsi.ObjSetAliasesReq(
                project_id=client.project_id,
                object_id="nonexistent_object",
                digest="0" * 64,
                aliases=["prod"],
            )
        )


def test_server_tag_on_deleted_object(client: WeaveClient):
    """Tags on deleted objects raise NotFoundError."""
    oid, digest = _publish_obj(client, "srv_err_deleted")
    client.server.obj_delete(
        tsi.ObjDeleteReq(
            project_id=client.project_id,
            object_id=oid,
            digests=[digest],
        )
    )
    with pytest.raises(NotFoundError):
        client.server.obj_add_tags(
            tsi.ObjAddTagsReq(
                project_id=client.project_id,
                object_id=oid,
                digest=digest,
                tags=["should-fail"],
            )
        )


def test_server_alias_on_deleted_object(client: WeaveClient):
    """Aliases on deleted objects raise NotFoundError."""
    oid, digest = _publish_obj(client, "srv_err_deleted2")
    client.server.obj_delete(
        tsi.ObjDeleteReq(
            project_id=client.project_id,
            object_id=oid,
            digests=[digest],
        )
    )
    with pytest.raises(NotFoundError):
        client.server.obj_set_aliases(
            tsi.ObjSetAliasesReq(
                project_id=client.project_id,
                object_id=oid,
                digest=digest,
                aliases=["should-fail"],
            )
        )


# ---------------------------------------------------------------------------
# Server-level enrichment
# ---------------------------------------------------------------------------


def test_server_enrichment(client: WeaveClient):
    """Enrichment toggle: None when off, populated when on, empty lists for untagged objects."""
    oid, digest = _publish_obj(client, "srv_enrich")

    client.server.obj_add_tags(
        tsi.ObjAddTagsReq(
            project_id=client.project_id,
            object_id=oid,
            digest=digest,
            tags=["reviewed"],
        )
    )
    client.server.obj_set_aliases(
        tsi.ObjSetAliasesReq(
            project_id=client.project_id,
            object_id=oid,
            digest=digest,
            aliases=["prod"],
        )
    )

    # Without enrichment — tags/aliases are None
    res = client.server.objs_query(
        tsi.ObjQueryReq(
            project_id=client.project_id,
            filter=tsi.ObjectVersionFilter(object_ids=[oid]),
        )
    )
    assert res.objs[0].tags is None
    assert res.objs[0].aliases is None

    read_res = client.server.obj_read(
        tsi.ObjReadReq(
            project_id=client.project_id,
            object_id=oid,
            digest=digest,
        )
    )
    assert read_res.obj.tags is None
    assert read_res.obj.aliases is None

    # With enrichment — tags/aliases populated
    res = client.server.objs_query(
        tsi.ObjQueryReq(
            project_id=client.project_id,
            filter=tsi.ObjectVersionFilter(object_ids=[oid]),
            include_tags_and_aliases=True,
        )
    )
    assert res.objs[0].tags == ["reviewed"]
    assert "prod" in res.objs[0].aliases
    assert "latest" in res.objs[0].aliases

    read_res = client.server.obj_read(
        tsi.ObjReadReq(
            project_id=client.project_id,
            object_id=oid,
            digest=digest,
            include_tags_and_aliases=True,
        )
    )
    assert read_res.obj.tags == ["reviewed"]
    assert "prod" in read_res.obj.aliases
    assert "latest" in read_res.obj.aliases

    # Object with no tags/aliases — enrichment returns empty lists
    oid2, digest2 = _publish_obj(client, "srv_enrich_empty")
    read_res = client.server.obj_read(
        tsi.ObjReadReq(
            project_id=client.project_id,
            object_id=oid2,
            digest=digest2,
            include_tags_and_aliases=True,
        )
    )
    assert read_res.obj.tags == []
    assert read_res.obj.aliases == ["latest"]

    # Multi-version enrichment: latest vs non-latest
    weave.publish({"v": 0}, name="srv_enrich_multi")
    weave.publish({"v": 1}, name="srv_enrich_multi")
    res = client.server.objs_query(
        tsi.ObjQueryReq(
            project_id=client.project_id,
            filter=tsi.ObjectVersionFilter(object_ids=["srv_enrich_multi"]),
            sort_by=[tsi.SortBy(field="created_at", direction="asc")],
            include_tags_and_aliases=True,
        )
    )
    v0, v1 = res.objs[0], res.objs[1]
    assert "latest" not in (v0.aliases or [])
    assert "latest" in v1.aliases

    # obj_read on older version: has real alias but NOT "latest"
    client.server.obj_set_aliases(
        tsi.ObjSetAliasesReq(
            project_id=client.project_id,
            object_id=v0.object_id,
            digest=v0.digest,
            aliases=["stable"],
        )
    )
    read_v0 = client.server.obj_read(
        tsi.ObjReadReq(
            project_id=client.project_id,
            object_id=v0.object_id,
            digest=v0.digest,
            include_tags_and_aliases=True,
        )
    )
    assert "stable" in read_v0.obj.aliases
    assert "latest" not in read_v0.obj.aliases


# ---------------------------------------------------------------------------
# Server-level obj_read with various digest types
# ---------------------------------------------------------------------------


def test_server_obj_read_digest_types(client: WeaveClient):
    """obj_read with real digest, alias, 'latest', and nonexistent alias."""
    oid, digest = _publish_obj(client, "srv_read_digest")

    # Real content-hash digest
    res = client.server.obj_read(
        tsi.ObjReadReq(
            project_id=client.project_id,
            object_id=oid,
            digest=digest,
        )
    )
    assert res.obj.digest == digest
    assert res.obj.object_id == oid

    # Alias resolution
    client.server.obj_set_aliases(
        tsi.ObjSetAliasesReq(
            project_id=client.project_id,
            object_id=oid,
            digest=digest,
            aliases=["production"],
        )
    )
    client.server.obj_set_aliases(
        tsi.ObjSetAliasesReq(
            project_id=client.project_id,
            object_id=oid,
            digest=digest,
            aliases=["stable"],
        )
    )
    res = client.server.obj_read(
        tsi.ObjReadReq(
            project_id=client.project_id,
            object_id=oid,
            digest="production",
            include_tags_and_aliases=True,
        )
    )
    assert res.obj.digest == digest
    assert "production" in res.obj.aliases
    assert "stable" in res.obj.aliases
    assert "latest" in res.obj.aliases

    # "latest" digest — resolves to latest version
    weave.publish({"v": 0}, name="srv_read_latest")
    weave.publish({"v": 1}, name="srv_read_latest")
    latest_q = client.server.objs_query(
        tsi.ObjQueryReq(
            project_id=client.project_id,
            filter=tsi.ObjectVersionFilter(
                object_ids=["srv_read_latest"],
                latest_only=True,
            ),
        )
    )
    v1 = latest_q.objs[0]
    client.server.obj_add_tags(
        tsi.ObjAddTagsReq(
            project_id=client.project_id,
            object_id=v1.object_id,
            digest=v1.digest,
            tags=["deployed"],
        )
    )
    read_res = client.server.obj_read(
        tsi.ObjReadReq(
            project_id=client.project_id,
            object_id="srv_read_latest",
            digest="latest",
            include_tags_and_aliases=True,
        )
    )
    assert read_res.obj.version_index == 1
    assert read_res.obj.tags == ["deployed"]
    assert "latest" in read_res.obj.aliases

    # Nonexistent alias raises NotFoundError
    with pytest.raises(NotFoundError):
        client.server.obj_read(
            tsi.ObjReadReq(
                project_id=client.project_id,
                object_id=oid,
                digest="nonexistent-alias",
            )
        )


# ---------------------------------------------------------------------------
# Server-level query filtering
# ---------------------------------------------------------------------------


def test_server_filter_by_tags(client: WeaveClient):
    """Filter by tags: single, multiple, nonexistent, empty list."""
    oid1, d1 = _publish_obj(client, "srv_ftag_a")
    oid2, d2 = _publish_obj(client, "srv_ftag_b")
    _publish_obj(client, "srv_ftag_c")  # no tags

    client.server.obj_add_tags(
        tsi.ObjAddTagsReq(
            project_id=client.project_id,
            object_id=oid1,
            digest=d1,
            tags=["alpha"],
        )
    )
    client.server.obj_add_tags(
        tsi.ObjAddTagsReq(
            project_id=client.project_id,
            object_id=oid2,
            digest=d2,
            tags=["beta"],
        )
    )

    # Single tag filter
    res = client.server.objs_query(
        tsi.ObjQueryReq(
            project_id=client.project_id,
            filter=tsi.ObjectVersionFilter(tags=["alpha"]),
        )
    )
    assert len(res.objs) == 1
    assert res.objs[0].object_id == oid1

    # Multiple tags — returns objects matching any
    res = client.server.objs_query(
        tsi.ObjQueryReq(
            project_id=client.project_id,
            filter=tsi.ObjectVersionFilter(tags=["alpha", "beta"]),
        )
    )
    assert {o.object_id for o in res.objs} == {oid1, oid2}

    # Nonexistent tag — empty result
    res = client.server.objs_query(
        tsi.ObjQueryReq(
            project_id=client.project_id,
            filter=tsi.ObjectVersionFilter(tags=["does-not-exist"]),
        )
    )
    assert len(res.objs) == 0

    # Empty tags list — no filter applied
    res = client.server.objs_query(
        tsi.ObjQueryReq(
            project_id=client.project_id,
            filter=tsi.ObjectVersionFilter(object_ids=[oid1], tags=[]),
        )
    )
    assert len(res.objs) >= 1


def test_server_filter_by_aliases(client: WeaveClient):
    """Filter by aliases: custom alias, 'latest', nonexistent, specific version only."""
    oid, digest = _publish_obj(client, "srv_falias")
    _publish_obj(client, "srv_falias_other")

    client.server.obj_set_aliases(
        tsi.ObjSetAliasesReq(
            project_id=client.project_id,
            object_id=oid,
            digest=digest,
            aliases=["production"],
        )
    )

    # Custom alias filter
    res = client.server.objs_query(
        tsi.ObjQueryReq(
            project_id=client.project_id,
            filter=tsi.ObjectVersionFilter(aliases=["production"]),
        )
    )
    assert len(res.objs) == 1
    assert res.objs[0].object_id == oid

    # Filter by 'latest' — returns only latest version
    weave.publish({"v": 0}, name="srv_falias_latest")
    weave.publish({"v": 1}, name="srv_falias_latest")
    res = client.server.objs_query(
        tsi.ObjQueryReq(
            project_id=client.project_id,
            filter=tsi.ObjectVersionFilter(
                object_ids=["srv_falias_latest"],
                aliases=["latest"],
            ),
            include_tags_and_aliases=True,
        )
    )
    assert len(res.objs) == 1
    assert "latest" in res.objs[0].aliases

    # Alias returns only the specific aliased version, not all versions
    weave.publish({"v": 0}, name="srv_falias_specific")
    weave.publish({"v": 1}, name="srv_falias_specific")
    weave.publish({"v": 2}, name="srv_falias_specific")
    all_res = client.server.objs_query(
        tsi.ObjQueryReq(
            project_id=client.project_id,
            filter=tsi.ObjectVersionFilter(object_ids=["srv_falias_specific"]),
            sort_by=[tsi.SortBy(field="created_at", direction="asc")],
        )
    )
    v1 = all_res.objs[1]
    client.server.obj_set_aliases(
        tsi.ObjSetAliasesReq(
            project_id=client.project_id,
            object_id=v1.object_id,
            digest=v1.digest,
            aliases=["pinned"],
        )
    )
    filtered = client.server.objs_query(
        tsi.ObjQueryReq(
            project_id=client.project_id,
            filter=tsi.ObjectVersionFilter(aliases=["pinned"]),
        )
    )
    assert len(filtered.objs) == 1
    assert filtered.objs[0].digest == v1.digest
    assert filtered.objs[0].version_index == 1

    # Nonexistent alias — empty result
    res = client.server.objs_query(
        tsi.ObjQueryReq(
            project_id=client.project_id,
            filter=tsi.ObjectVersionFilter(aliases=["does-not-exist"]),
        )
    )
    assert len(res.objs) == 0


def test_server_filter_combined_tags_and_aliases(client: WeaveClient):
    """Filtering with both tags and aliases simultaneously ANDs the conditions."""
    oid1, d1 = _publish_obj(client, "srv_combo1")
    oid2, d2 = _publish_obj(client, "srv_combo2")
    oid3, d3 = _publish_obj(client, "srv_combo3")

    # obj1: has tag "reviewed" AND alias "production"
    client.server.obj_add_tags(
        tsi.ObjAddTagsReq(
            project_id=client.project_id,
            object_id=oid1,
            digest=d1,
            tags=["reviewed"],
        )
    )
    client.server.obj_set_aliases(
        tsi.ObjSetAliasesReq(
            project_id=client.project_id,
            object_id=oid1,
            digest=d1,
            aliases=["production"],
        )
    )

    # obj2: has tag "reviewed" but no alias "production"
    client.server.obj_add_tags(
        tsi.ObjAddTagsReq(
            project_id=client.project_id,
            object_id=oid2,
            digest=d2,
            tags=["reviewed"],
        )
    )

    # obj3: has alias "production" but no tag "reviewed"
    client.server.obj_set_aliases(
        tsi.ObjSetAliasesReq(
            project_id=client.project_id,
            object_id=oid3,
            digest=d3,
            aliases=["production"],
        )
    )

    res = client.server.objs_query(
        tsi.ObjQueryReq(
            project_id=client.project_id,
            filter=tsi.ObjectVersionFilter(
                tags=["reviewed"],
                aliases=["production"],
            ),
        )
    )
    assert len(res.objs) == 1
    assert res.objs[0].object_id == oid1


# ---------------------------------------------------------------------------
# Server-level version/object isolation
# ---------------------------------------------------------------------------


def test_server_version_and_object_isolation(client: WeaveClient):
    """Tags scoped to version, aliases across versions, latest virtual, cross-object isolation."""
    # Tags scoped to version
    weave.publish({"v": 0}, name="srv_iso_ver")
    weave.publish({"v": 1}, name="srv_iso_ver")
    res = client.server.objs_query(
        tsi.ObjQueryReq(
            project_id=client.project_id,
            filter=tsi.ObjectVersionFilter(object_ids=["srv_iso_ver"]),
            sort_by=[tsi.SortBy(field="created_at", direction="asc")],
        )
    )
    v0, v1 = res.objs[0], res.objs[1]

    client.server.obj_add_tags(
        tsi.ObjAddTagsReq(
            project_id=client.project_id,
            object_id=v0.object_id,
            digest=v0.digest,
            tags=["v0-only"],
        )
    )
    res = client.server.objs_query(
        tsi.ObjQueryReq(
            project_id=client.project_id,
            filter=tsi.ObjectVersionFilter(object_ids=["srv_iso_ver"]),
            include_tags_and_aliases=True,
            sort_by=[tsi.SortBy(field="created_at", direction="asc")],
        )
    )
    assert "v0-only" in res.objs[0].tags
    assert res.objs[1].tags == []

    # Different aliases on different versions
    client.server.obj_set_aliases(
        tsi.ObjSetAliasesReq(
            project_id=client.project_id,
            object_id=v0.object_id,
            digest=v0.digest,
            aliases=["stable"],
        )
    )
    client.server.obj_set_aliases(
        tsi.ObjSetAliasesReq(
            project_id=client.project_id,
            object_id=v1.object_id,
            digest=v1.digest,
            aliases=["canary"],
        )
    )
    res = client.server.objs_query(
        tsi.ObjQueryReq(
            project_id=client.project_id,
            filter=tsi.ObjectVersionFilter(object_ids=["srv_iso_ver"]),
            include_tags_and_aliases=True,
            sort_by=[tsi.SortBy(field="created_at", direction="asc")],
        )
    )
    assert "stable" in res.objs[0].aliases
    assert "canary" not in (res.objs[0].aliases or [])
    assert "canary" in res.objs[1].aliases
    assert "stable" not in (res.objs[1].aliases or [])

    # Cross-object isolation: tags/aliases don't leak between objects
    oid_a, digest_a = _publish_obj(client, "srv_iso_a")
    oid_b, digest_b = _publish_obj(client, "srv_iso_b")

    client.server.obj_add_tags(
        tsi.ObjAddTagsReq(
            project_id=client.project_id,
            object_id=oid_a,
            digest=digest_a,
            tags=["only-on-a"],
        )
    )
    client.server.obj_set_aliases(
        tsi.ObjSetAliasesReq(
            project_id=client.project_id,
            object_id=oid_b,
            digest=digest_b,
            aliases=["only-on-b"],
        )
    )
    res = client.server.objs_query(
        tsi.ObjQueryReq(
            project_id=client.project_id,
            filter=tsi.ObjectVersionFilter(object_ids=[oid_a, oid_b]),
            include_tags_and_aliases=True,
        )
    )
    objs_by_id = {o.object_id: o for o in res.objs}
    assert "only-on-a" in objs_by_id[oid_a].tags
    assert "only-on-a" not in objs_by_id[oid_b].tags
    assert "only-on-b" in objs_by_id[oid_b].aliases
    assert "only-on-b" not in (objs_by_id[oid_a].aliases or [])


def test_server_batch_enrichment(client: WeaveClient):
    """Enrichment of 3+ distinct objects in one objs_query call."""
    oid1, d1 = _publish_obj(client, "srv_batch_a")
    oid2, d2 = _publish_obj(client, "srv_batch_b")
    oid3, d3 = _publish_obj(client, "srv_batch_c")

    client.server.obj_add_tags(
        tsi.ObjAddTagsReq(
            project_id=client.project_id,
            object_id=oid1,
            digest=d1,
            tags=["alpha"],
        )
    )
    client.server.obj_set_aliases(
        tsi.ObjSetAliasesReq(
            project_id=client.project_id,
            object_id=oid1,
            digest=d1,
            aliases=["prod"],
        )
    )
    client.server.obj_add_tags(
        tsi.ObjAddTagsReq(
            project_id=client.project_id,
            object_id=oid2,
            digest=d2,
            tags=["beta"],
        )
    )
    client.server.obj_set_aliases(
        tsi.ObjSetAliasesReq(
            project_id=client.project_id,
            object_id=oid3,
            digest=d3,
            aliases=["canary"],
        )
    )

    res = client.server.objs_query(
        tsi.ObjQueryReq(
            project_id=client.project_id,
            filter=tsi.ObjectVersionFilter(object_ids=[oid1, oid2, oid3]),
            include_tags_and_aliases=True,
        )
    )
    objs = {o.object_id: o for o in res.objs}
    assert len(objs) == 3

    assert objs[oid1].tags == ["alpha"]
    assert "prod" in objs[oid1].aliases
    assert "latest" in objs[oid1].aliases

    assert objs[oid2].tags == ["beta"]
    assert objs[oid2].aliases == ["latest"]

    assert objs[oid3].tags == []
    assert "canary" in objs[oid3].aliases
    assert "latest" in objs[oid3].aliases


# ---------------------------------------------------------------------------
# Server-level list endpoints
# ---------------------------------------------------------------------------


def test_server_list_endpoints(client: WeaveClient):
    """List tags and aliases: empty project, distinct sorted, excludes removed."""
    # Empty project
    assert (
        client.server.tags_list(tsi.TagsListReq(project_id=client.project_id)).tags
        == []
    )
    assert (
        client.server.aliases_list(
            tsi.AliasesListReq(project_id=client.project_id)
        ).aliases
        == []
    )

    # Add overlapping tags/aliases across objects
    oid1, d1 = _publish_obj(client, "srv_list_1")
    oid2, d2 = _publish_obj(client, "srv_list_2")

    client.server.obj_add_tags(
        tsi.ObjAddTagsReq(
            project_id=client.project_id,
            object_id=oid1,
            digest=d1,
            tags=["beta", "alpha"],
        )
    )
    client.server.obj_add_tags(
        tsi.ObjAddTagsReq(
            project_id=client.project_id,
            object_id=oid2,
            digest=d2,
            tags=["alpha", "gamma"],
        )
    )
    res = client.server.tags_list(tsi.TagsListReq(project_id=client.project_id))
    assert res.tags == ["alpha", "beta", "gamma"]

    client.server.obj_set_aliases(
        tsi.ObjSetAliasesReq(
            project_id=client.project_id,
            object_id=oid1,
            digest=d1,
            aliases=["production"],
        )
    )
    client.server.obj_set_aliases(
        tsi.ObjSetAliasesReq(
            project_id=client.project_id,
            object_id=oid2,
            digest=d2,
            aliases=["canary"],
        )
    )
    res = client.server.aliases_list(tsi.AliasesListReq(project_id=client.project_id))
    assert res.aliases == ["canary", "production"]

    # Removed tags/aliases don't appear
    client.server.obj_remove_tags(
        tsi.ObjRemoveTagsReq(
            project_id=client.project_id,
            object_id=oid1,
            digest=d1,
            tags=["beta"],
        )
    )
    client.server.obj_remove_aliases(
        tsi.ObjRemoveAliasesReq(
            project_id=client.project_id,
            object_id=oid1,
            aliases=["production"],
        )
    )
    res = client.server.tags_list(tsi.TagsListReq(project_id=client.project_id))
    assert "beta" not in res.tags
    assert "alpha" in res.tags
    res = client.server.aliases_list(tsi.AliasesListReq(project_id=client.project_id))
    assert "production" not in res.aliases
    assert "canary" in res.aliases


# ---------------------------------------------------------------------------
# SDK client tag lifecycle
# ---------------------------------------------------------------------------


def test_sdk_tag_lifecycle(client: WeaveClient):
    """SDK client tag operations: add, remove, get, idempotent, re-add, scoped, multiple, list."""
    ref = weave.publish({"data": "test"}, name="sdk_tags")

    # Add and get
    client.add_tags(ref, ["alpha", "beta"])
    assert client.get_tags(ref) == ["alpha", "beta"]

    # Remove
    client.remove_tags(ref, ["alpha"])
    assert client.get_tags(ref) == ["beta"]

    # Get on fresh object returns empty
    ref2 = weave.publish({"data": "test2"}, name="sdk_tags_empty")
    assert client.get_tags(ref2) == []

    # Idempotent add
    client.add_tags(ref, ["beta"])
    client.add_tags(ref, ["beta"])
    assert client.get_tags(ref) == ["beta"]

    # Re-add after removal
    client.remove_tags(ref, ["beta"])
    assert client.get_tags(ref) == []
    client.add_tags(ref, ["beta"])
    assert client.get_tags(ref) == ["beta"]

    # Remove nonexistent — silent
    client.remove_tags(ref, ["never-added"])
    assert client.get_tags(ref) == ["beta"]

    # Tags scoped to version
    ref_v0 = weave.publish({"v": 0}, name="sdk_tags_scope")
    ref_v1 = weave.publish({"v": 1}, name="sdk_tags_scope")
    client.add_tags(ref_v0, ["v0-only"])
    assert "v0-only" in client.get_tags(ref_v0)
    assert client.get_tags(ref_v1) == []

    # Multiple tags and aliases simultaneously
    ref3 = weave.publish({"data": "test3"}, name="sdk_tags_multi")
    client.add_tags(ref3, ["reviewed", "production", "v2"])
    tags = client.get_tags(ref3)
    assert tags == ["production", "reviewed", "v2"]

    # List tags (+ excludes removed)
    ref4 = weave.publish({"data": "test4"}, name="sdk_tags_list")
    client.add_tags(ref4, ["keep", "remove-me"])
    client.remove_tags(ref4, ["remove-me"])
    all_tags = client.list_tags()
    assert "keep" in all_tags
    assert "remove-me" not in all_tags
    assert all_tags == sorted(all_tags)


# ---------------------------------------------------------------------------
# SDK client alias lifecycle
# ---------------------------------------------------------------------------


def test_sdk_alias_lifecycle(client: WeaveClient):
    """SDK client alias operations: set, remove, get, reassign, list, string/list variants."""
    ref = weave.publish({"data": "test"}, name="sdk_aliases")

    # Set (string) and get
    client.set_aliases(ref, "production")
    aliases = client.get_aliases(ref)
    assert "production" in aliases
    assert "latest" in aliases

    # Remove
    client.remove_aliases(ref, "production")
    assert "production" not in client.get_aliases(ref)

    # Remove nonexistent — silent
    client.remove_aliases(ref, "never-set")

    # Reassignment across versions
    ref_v0 = weave.publish({"v": 0}, name="sdk_alias_reassign")
    ref_v1 = weave.publish({"v": 1}, name="sdk_alias_reassign")
    client.set_aliases(ref_v0, "staging")
    assert "staging" in client.get_aliases(ref_v0)
    client.set_aliases(ref_v1, "staging")
    assert "staging" not in client.get_aliases(ref_v0)
    assert "staging" in client.get_aliases(ref_v1)

    # Set with list
    ref2 = weave.publish({"data": "test2"}, name="sdk_alias_list")
    client.set_aliases(ref2, ["alpha", "beta", "gamma"])
    aliases = client.get_aliases(ref2)
    assert "alpha" in aliases
    assert "beta" in aliases
    assert "gamma" in aliases

    # Set with single-element list
    ref3 = weave.publish({"data": "test3"}, name="sdk_alias_single")
    time.sleep(0.2)
    client.set_aliases(ref3, ["only-one"])
    assert "only-one" in client.get_aliases(ref3)

    # Set with empty list — no-op
    ref4 = weave.publish({"data": "test4"}, name="sdk_alias_empty")
    client.set_aliases(ref4, [])
    assert client.get_aliases(ref4) == ["latest"]

    # Multiple aliases on same object
    client.set_aliases(ref, "prod")
    client.set_aliases(ref, "stable")
    aliases = client.get_aliases(ref)
    assert "prod" in aliases
    assert "stable" in aliases
    assert "latest" in aliases

    # List aliases (+ excludes removed)
    ref5 = weave.publish({"data": "test5"}, name="sdk_alias_list_check")
    client.set_aliases(ref5, "keep-alias")
    client.set_aliases(ref5, "remove-alias")
    client.remove_aliases(ref5, "remove-alias")
    all_aliases = client.list_aliases()
    assert "keep-alias" in all_aliases
    assert "remove-alias" not in all_aliases
    assert all_aliases == sorted(all_aliases)


# ---------------------------------------------------------------------------
# SDK URI string acceptance
# ---------------------------------------------------------------------------


def test_sdk_uri_strings(client: WeaveClient):
    """All SDK tag/alias methods accept weave:/// URI strings alongside ObjectRef."""
    ref = weave.publish({"data": "test"}, name="sdk_uri")
    uri = ref.uri

    # Tags: add via URI, get via ref; get via URI
    client.add_tags(uri, ["from-uri"])
    assert client.get_tags(ref) == ["from-uri"]
    assert client.get_tags(uri) == ["from-uri"]

    # Tags: remove via URI
    client.add_tags(ref, ["remove-me"])
    client.remove_tags(uri, ["remove-me"])
    assert client.get_tags(ref) == ["from-uri"]

    # Aliases: set via URI, get via ref; get via URI
    client.set_aliases(uri, "production")
    assert "production" in client.get_aliases(ref)
    assert "production" in client.get_aliases(uri)

    # Aliases: remove via URI
    client.remove_aliases(uri, "production")
    assert "production" not in client.get_aliases(ref)

    # Mixed: add via URI, get via ref (and vice versa)
    client.add_tags(uri, ["mixed-tag"])
    assert "mixed-tag" in client.get_tags(ref)

    client.set_aliases(uri, "mixed-alias")
    assert "mixed-alias" in client.get_aliases(ref)


# ---------------------------------------------------------------------------
# SDK errors on nonexistent objects
# ---------------------------------------------------------------------------


def test_sdk_add_tags_error_nonexistent(client: WeaveClient):
    """SDK add_tags raises NotFoundError on fake ref."""
    fake_ref = ObjectRef(
        entity="test",
        project="test",
        name="nonexistent_object",
        _digest="0" * 43,
    )
    with pytest.raises(NotFoundError):
        client.add_tags(fake_ref, ["tag"])


def test_sdk_set_aliases_error_nonexistent(client: WeaveClient):
    """SDK set_aliases raises NotFoundError on fake ref."""
    fake_ref = ObjectRef(
        entity="test",
        project="test",
        name="nonexistent_object",
        _digest="0" * 43,
    )
    with pytest.raises(NotFoundError):
        client.set_aliases(fake_ref, "prod")


# ---------------------------------------------------------------------------
# Top-level weave.* wrapper functions
# ---------------------------------------------------------------------------


def test_weave_tag_functions(client: WeaveClient):
    """weave.add_tags, remove_tags, get_tags, list_tags — full lifecycle."""
    ref = weave.publish({"data": "test"}, name="tl_tags")

    # Add and get
    weave.add_tags(ref, ["top-level-tag", "another"])
    assert "top-level-tag" in weave.get_tags(ref)

    # Remove
    weave.remove_tags(ref, ["another"])
    tags = weave.get_tags(ref)
    assert "top-level-tag" in tags
    assert "another" not in tags

    # Empty add/remove are no-ops
    weave.add_tags(ref, [])
    assert weave.get_tags(ref) == ["top-level-tag"]
    weave.remove_tags(ref, [])
    assert weave.get_tags(ref) == ["top-level-tag"]

    # Bulk add and remove
    ref2 = weave.publish({"data": "test2"}, name="tl_tags_bulk")
    weave.add_tags(ref2, ["a", "b", "c", "d", "e"])
    assert weave.get_tags(ref2) == ["a", "b", "c", "d", "e"]
    weave.remove_tags(ref2, ["b", "d"])
    assert weave.get_tags(ref2) == ["a", "c", "e"]

    # Tags returned sorted
    ref3 = weave.publish({"data": "test3"}, name="tl_tags_sorted")
    weave.add_tags(ref3, ["zulu", "alpha", "mike"])
    assert weave.get_tags(ref3) == sorted(weave.get_tags(ref3))

    # Tags from publish() and add_tags() combine
    ref4 = weave.publish(
        {"data": "test4"}, name="tl_tags_combine", tags=["from-publish"]
    )
    weave.add_tags(ref4, ["from-add"])
    tags = weave.get_tags(ref4)
    assert "from-publish" in tags
    assert "from-add" in tags

    # Independent across objects
    ref_a = weave.publish({"obj": "a"}, name="tl_tags_indep_a")
    ref_b = weave.publish({"obj": "b"}, name="tl_tags_indep_b")
    weave.add_tags(ref_a, ["only-on-a"])
    assert weave.get_tags(ref_a) == ["only-on-a"]
    assert weave.get_tags(ref_b) == []

    # Per-version independence
    ref_v0 = weave.publish({"v": 0}, name="tl_tags_ver")
    ref_v1 = weave.publish({"v": 1}, name="tl_tags_ver")
    ref_v2 = weave.publish({"v": 2}, name="tl_tags_ver")
    weave.add_tags(ref_v0, ["old"])
    weave.add_tags(ref_v1, ["stable", "reviewed"])
    assert weave.get_tags(ref_v0) == ["old"]
    assert weave.get_tags(ref_v1) == ["reviewed", "stable"]
    assert weave.get_tags(ref_v2) == []

    # Tags survive ref.get roundtrip
    ref5 = weave.publish({"data": "tagged"}, name="tl_tags_roundtrip")
    weave.add_tags(ref5, ["important", "reviewed"])
    weave.ref("tl_tags_roundtrip:latest").get()
    assert weave.get_tags(ref5) == ["important", "reviewed"]

    # list_tags: across objects, deduplicated
    all_tags = weave.list_tags()
    assert "only-on-a" in all_tags
    assert all_tags.count("only-on-a") == 1


def test_weave_alias_functions(client: WeaveClient):
    """weave.set_aliases, remove_aliases, get_aliases, list_aliases — full lifecycle."""
    ref = weave.publish({"data": "test"}, name="tl_aliases")

    # Set (string) and get
    weave.set_aliases(ref, "top-level-alias")
    assert "top-level-alias" in weave.get_aliases(ref)

    # Set (list)
    weave.set_aliases(ref, ["alias-a", "alias-b"])
    aliases = weave.get_aliases(ref)
    assert "alias-a" in aliases
    assert "alias-b" in aliases

    # Remove
    weave.remove_aliases(ref, "top-level-alias")
    assert "top-level-alias" not in weave.get_aliases(ref)

    # Per-version independence
    ref_v0 = weave.publish({"v": 0}, name="tl_alias_ver")
    ref_v1 = weave.publish({"v": 1}, name="tl_alias_ver")
    weave.set_aliases(ref_v0, "old-stable")
    weave.set_aliases(ref_v1, "current")
    assert "old-stable" in weave.get_aliases(ref_v0)
    assert "current" not in weave.get_aliases(ref_v0)
    assert "current" in weave.get_aliases(ref_v1)
    assert "old-stable" not in weave.get_aliases(ref_v1)

    # Same alias on different objects — independent
    ref_a = weave.publish({"obj": "a"}, name="tl_alias_indep_a")
    ref_b = weave.publish({"obj": "b"}, name="tl_alias_indep_b")
    weave.set_aliases(ref_a, "prod")
    weave.set_aliases(ref_b, "prod")
    assert "prod" in weave.get_aliases(ref_a)
    assert "prod" in weave.get_aliases(ref_b)
    weave.remove_aliases(ref_a, "prod")
    assert "prod" not in weave.get_aliases(ref_a)
    assert "prod" in weave.get_aliases(ref_b)

    # Virtual 'latest'
    ref_c = weave.publish({"v": 0}, name="tl_alias_latest")
    assert "latest" in weave.get_aliases(ref_c)
    ref_d = weave.publish({"v": 1}, name="tl_alias_latest")
    assert "latest" in weave.get_aliases(ref_d)

    # list_aliases: across objects, deduplicated (use fresh alias to avoid
    # interaction with the partial removal of "prod" above)
    ref_x = weave.publish({"obj": "x"}, name="tl_alias_dedup_x")
    ref_y = weave.publish({"obj": "y"}, name="tl_alias_dedup_y")
    weave.set_aliases(ref_x, "shared-alias")
    weave.set_aliases(ref_y, "shared-alias")
    all_aliases = weave.list_aliases()
    assert "shared-alias" in all_aliases
    assert all_aliases.count("shared-alias") == 1

    # Remove alias then resolve raises
    ref_e = weave.publish({"data": "test"}, name="tl_alias_rm_resolve")
    client.set_aliases(ref_e, "temporary")
    assert weave.ref("tl_alias_rm_resolve:temporary").get()["data"] == "test"
    client.remove_aliases(ref_e, "temporary")
    with pytest.raises(NotFoundError):
        weave.ref("tl_alias_rm_resolve:temporary").get()


# ---------------------------------------------------------------------------
# Alias resolution via weave.ref() and weave.get()
# ---------------------------------------------------------------------------


def test_alias_resolution(client: WeaveClient):
    """Resolve by alias: latest, custom, reassignment, publish-time, implicit, nonexistent, digest check."""
    # latest alias
    weave.publish({"v": 0}, name="resolve_obj")
    weave.publish({"v": 1}, name="resolve_obj")
    assert weave.ref("resolve_obj:latest").get()["v"] == 1

    # Implicit latest (no version specifier)
    assert weave.ref("resolve_obj").get()["v"] == 1

    # Custom alias
    ref_v0 = weave.publish({"v": 0}, name="resolve_custom")
    weave.publish({"v": 1}, name="resolve_custom")
    client.set_aliases(ref_v0, "production")
    assert weave.ref("resolve_custom:production").get()["v"] == 0

    # weave.get with alias string
    assert weave.get("resolve_custom:production")["v"] == 0

    # Reassignment
    ref_r0 = weave.publish({"v": 0}, name="resolve_reassign")
    ref_r1 = weave.publish({"v": 1}, name="resolve_reassign")
    client.set_aliases(ref_r0, "staging")
    assert weave.ref("resolve_reassign:staging").get()["v"] == 0
    client.set_aliases(ref_r1, "staging")
    assert weave.ref("resolve_reassign:staging").get()["v"] == 1

    # Alias set at publish time
    weave.publish({"v": 0}, name="resolve_pub")
    weave.publish({"v": 1}, name="resolve_pub", aliases=["stable"])
    weave.publish({"v": 2}, name="resolve_pub")
    assert weave.ref("resolve_pub:stable").get()["v"] == 1
    assert weave.ref("resolve_pub:latest").get()["v"] == 2

    # Nonexistent alias raises
    weave.publish({"v": 0}, name="resolve_noexist")
    with pytest.raises(NotFoundError):
        weave.ref("resolve_noexist:nonexistent").get()

    # Resolved ref has real content digest, not the alias
    ref_check = weave.publish({"v": 0}, name="resolve_digest")
    client.set_aliases(ref_check, "check-me")
    obj = weave.ref("resolve_digest:check-me").get()
    assert obj.ref.digest == ref_check.digest
    assert obj.ref.digest != "check-me"

    # Multiple aliases on same version all resolve
    ref_multi = weave.publish({"v": 0}, name="resolve_multi")
    client.set_aliases(ref_multi, ["alpha", "beta", "gamma"])
    for alias in ["alpha", "beta", "gamma"]:
        assert weave.ref(f"resolve_multi:{alias}").get()["v"] == 0


# ---------------------------------------------------------------------------
# Full end-to-end lifecycle
# ---------------------------------------------------------------------------


def test_full_lifecycle(client: WeaveClient):
    """Comprehensive lifecycle: publish, tag, alias, resolve, reassign, remove, verify lists."""
    ref_v0 = weave.publish({"v": 0}, name="lifecycle_obj")
    ref_v1 = weave.publish({"v": 1}, name="lifecycle_obj")

    # Tag both
    weave.add_tags(ref_v0, ["deprecated"])
    weave.add_tags(ref_v1, ["stable", "reviewed"])

    # Alias v1 as production
    weave.set_aliases(ref_v1, "production")
    assert weave.ref("lifecycle_obj:production").get()["v"] == 1

    # Verify tags/aliases
    assert weave.get_tags(ref_v0) == ["deprecated"]
    assert weave.get_tags(ref_v1) == ["reviewed", "stable"]
    assert "production" in weave.get_aliases(ref_v1)

    # Reassign alias to v0
    weave.set_aliases(ref_v0, "production")
    assert weave.ref("lifecycle_obj:production").get()["v"] == 0
    assert "production" not in weave.get_aliases(ref_v1)

    # Remove tags
    weave.remove_tags(ref_v0, ["deprecated"])
    assert weave.get_tags(ref_v0) == []

    # Remove alias — resolve should fail
    weave.remove_aliases(ref_v0, "production")
    with pytest.raises(NotFoundError):
        weave.ref("lifecycle_obj:production").get()

    # list_tags/list_aliases reflect current state
    all_tags = weave.list_tags()
    assert "deprecated" not in all_tags
    assert "stable" in all_tags
    assert "reviewed" in all_tags


def test_publish_with_tags_and_aliases(client: WeaveClient):
    """Tags and aliases set at publish time work with resolution."""
    weave.publish({"v": 0}, name="pub_resolve")
    weave.publish(
        {"v": 1},
        name="pub_resolve",
        tags=["release-candidate"],
        aliases=["rc"],
    )
    weave.publish({"v": 2}, name="pub_resolve")

    assert weave.ref("pub_resolve:rc").get()["v"] == 1
    assert weave.ref("pub_resolve:latest").get()["v"] == 2


# ---------------------------------------------------------------------------
# Cross-project isolation
# ---------------------------------------------------------------------------


def test_cross_project_isolation(client: WeaveClient):
    """Tags, aliases, lists, and resolution are all scoped to their project."""
    server = client.server
    proj_a = "test-entity/proj-iso-a"
    proj_b = "test-entity/proj-iso-b"

    _, digest_a = _create_obj_in_project(server, proj_a, "shared_obj", {"proj": "a"})
    _, digest_b = _create_obj_in_project(server, proj_b, "shared_obj", {"proj": "b"})

    # Tag only project A
    server.obj_add_tags(
        tsi.ObjAddTagsReq(
            project_id=proj_a,
            object_id="shared_obj",
            digest=digest_a,
            tags=["proj-a-only"],
        )
    )
    res_a = server.obj_read(
        tsi.ObjReadReq(
            project_id=proj_a,
            object_id="shared_obj",
            digest=digest_a,
            include_tags_and_aliases=True,
        )
    )
    assert "proj-a-only" in (res_a.obj.tags or [])
    res_b = server.obj_read(
        tsi.ObjReadReq(
            project_id=proj_b,
            object_id="shared_obj",
            digest=digest_b,
            include_tags_and_aliases=True,
        )
    )
    assert res_b.obj.tags is None or "proj-a-only" not in res_b.obj.tags

    # Alias only project A
    server.obj_set_aliases(
        tsi.ObjSetAliasesReq(
            project_id=proj_a,
            object_id="shared_obj",
            digest=digest_a,
            aliases=["production"],
        )
    )
    res_a = server.obj_read(
        tsi.ObjReadReq(
            project_id=proj_a,
            object_id="shared_obj",
            digest=digest_a,
            include_tags_and_aliases=True,
        )
    )
    assert "production" in (res_a.obj.aliases or [])
    res_b = server.obj_read(
        tsi.ObjReadReq(
            project_id=proj_b,
            object_id="shared_obj",
            digest=digest_b,
            include_tags_and_aliases=True,
        )
    )
    assert res_b.obj.aliases is None or "production" not in res_b.obj.aliases

    # List endpoints scoped
    tags_a = server.tags_list(tsi.TagsListReq(project_id=proj_a))
    tags_b = server.tags_list(tsi.TagsListReq(project_id=proj_b))
    assert "proj-a-only" in tags_a.tags
    assert "proj-a-only" not in tags_b.tags

    aliases_a = server.aliases_list(tsi.AliasesListReq(project_id=proj_a))
    aliases_b = server.aliases_list(tsi.AliasesListReq(project_id=proj_b))
    assert "production" in aliases_a.aliases
    assert "production" not in aliases_b.aliases

    # Alias resolution scoped
    res = server.obj_read(
        tsi.ObjReadReq(
            project_id=proj_a,
            object_id="shared_obj",
            digest="production",
            include_tags_and_aliases=True,
        )
    )
    assert res.obj.val == {"proj": "a"}
    with pytest.raises(NotFoundError):
        server.obj_read(
            tsi.ObjReadReq(
                project_id=proj_b,
                object_id="shared_obj",
                digest="production",
            )
        )


# ---------------------------------------------------------------------------
# Deletion cascades
# ---------------------------------------------------------------------------


def test_deletion_cascades(client: WeaveClient):
    """Deleting versions cleans up tags/aliases; surviving versions keep theirs."""
    # Specific version cleanup — tags
    oid, digest = _publish_obj(client, "del_cascade_tag")
    client.server.obj_add_tags(
        tsi.ObjAddTagsReq(
            project_id=client.project_id,
            object_id=oid,
            digest=digest,
            tags=["reviewed", "staging"],
        )
    )
    client.server.obj_delete(
        tsi.ObjDeleteReq(
            project_id=client.project_id,
            object_id=oid,
            digests=[digest],
        )
    )
    tags_res = client.server.tags_list(tsi.TagsListReq(project_id=client.project_id))
    assert "reviewed" not in tags_res.tags
    assert "staging" not in tags_res.tags

    # Specific version cleanup — aliases
    oid2, digest2 = _publish_obj(client, "del_cascade_alias")
    client.server.obj_set_aliases(
        tsi.ObjSetAliasesReq(
            project_id=client.project_id,
            object_id=oid2,
            digest=digest2,
            aliases=["production"],
        )
    )
    client.server.obj_delete(
        tsi.ObjDeleteReq(
            project_id=client.project_id,
            object_id=oid2,
            digests=[digest2],
        )
    )
    aliases_res = client.server.aliases_list(
        tsi.AliasesListReq(project_id=client.project_id)
    )
    assert "production" not in aliases_res.aliases
    with pytest.raises(NotFoundError):
        client.server.obj_read(
            tsi.ObjReadReq(
                project_id=client.project_id,
                object_id=oid2,
                digest="production",
            )
        )

    # Delete all versions — all tags/aliases cleaned up
    oid3, d3_0 = _publish_obj(client, "del_cascade_all")
    _, d3_1 = _publish_obj(client, "del_cascade_all", val={"data": "v2"})
    client.server.obj_add_tags(
        tsi.ObjAddTagsReq(
            project_id=client.project_id,
            object_id=oid3,
            digest=d3_0,
            tags=["v0-tag"],
        )
    )
    client.server.obj_add_tags(
        tsi.ObjAddTagsReq(
            project_id=client.project_id,
            object_id=oid3,
            digest=d3_1,
            tags=["v1-tag"],
        )
    )
    client.server.obj_set_aliases(
        tsi.ObjSetAliasesReq(
            project_id=client.project_id,
            object_id=oid3,
            digest=d3_0,
            aliases=["v0-alias"],
        )
    )
    client.server.obj_set_aliases(
        tsi.ObjSetAliasesReq(
            project_id=client.project_id,
            object_id=oid3,
            digest=d3_1,
            aliases=["v1-alias"],
        )
    )
    client.server.obj_delete(
        tsi.ObjDeleteReq(
            project_id=client.project_id,
            object_id=oid3,
        )
    )
    tags_res = client.server.tags_list(tsi.TagsListReq(project_id=client.project_id))
    assert "v0-tag" not in tags_res.tags
    assert "v1-tag" not in tags_res.tags
    aliases_res = client.server.aliases_list(
        tsi.AliasesListReq(project_id=client.project_id)
    )
    assert "v0-alias" not in aliases_res.aliases
    assert "v1-alias" not in aliases_res.aliases

    # Surviving version preserves its tags/aliases when sibling deleted
    oid4, d4_0 = _publish_obj(client, "del_cascade_survive")
    _, d4_1 = _publish_obj(client, "del_cascade_survive", val={"data": "v2"})
    client.server.obj_add_tags(
        tsi.ObjAddTagsReq(
            project_id=client.project_id,
            object_id=oid4,
            digest=d4_0,
            tags=["doomed"],
        )
    )
    client.server.obj_add_tags(
        tsi.ObjAddTagsReq(
            project_id=client.project_id,
            object_id=oid4,
            digest=d4_1,
            tags=["survivor"],
        )
    )
    client.server.obj_set_aliases(
        tsi.ObjSetAliasesReq(
            project_id=client.project_id,
            object_id=oid4,
            digest=d4_0,
            aliases=["doomed-alias"],
        )
    )
    client.server.obj_set_aliases(
        tsi.ObjSetAliasesReq(
            project_id=client.project_id,
            object_id=oid4,
            digest=d4_1,
            aliases=["survivor-alias"],
        )
    )
    client.server.obj_delete(
        tsi.ObjDeleteReq(
            project_id=client.project_id,
            object_id=oid4,
            digests=[d4_0],
        )
    )

    # v1's tags/aliases survive
    res = client.server.objs_query(
        tsi.ObjQueryReq(
            project_id=client.project_id,
            filter=tsi.ObjectVersionFilter(object_ids=[oid4]),
            include_tags_and_aliases=True,
        )
    )
    assert len(res.objs) == 1
    assert res.objs[0].tags == ["survivor"]
    assert "survivor-alias" in res.objs[0].aliases

    # v0's tags/aliases gone
    tags_res = client.server.tags_list(tsi.TagsListReq(project_id=client.project_id))
    assert "doomed" not in tags_res.tags
    assert "survivor" in tags_res.tags
    aliases_res = client.server.aliases_list(
        tsi.AliasesListReq(project_id=client.project_id)
    )
    assert "doomed-alias" not in aliases_res.aliases
    assert "survivor-alias" in aliases_res.aliases
