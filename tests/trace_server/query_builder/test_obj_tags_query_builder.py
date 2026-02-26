from weave.trace_server.query_builder.obj_tags_query_builder import (
    make_assert_obj_version_exists_query,
    make_get_aliases_query,
    make_get_tags_query,
    make_resolve_alias_query,
)
from weave.trace_server.query_builder.objects_query_builder import (
    ObjectMetadataQueryBuilder,
)


# --- obj_tags_query_builder functions ---


def test_make_assert_obj_version_exists_query():
    query, params = make_assert_obj_version_exists_query("proj", "obj1", "abc123")
    assert "object_versions" in query
    assert "argMax(deleted_at, created_at) IS NULL" in query
    assert params == {"project_id": "proj", "object_id": "obj1", "digest": "abc123"}


def test_make_get_tags_query():
    query, params = make_get_tags_query("proj", ["obj1", "obj2"])
    assert "FROM tags" in query
    assert "tag" in query
    assert params["project_id"] == "proj"
    assert set(params["object_ids"]) == {"obj1", "obj2"}
    assert "digests" not in params


def test_make_get_aliases_query():
    query, params = make_get_aliases_query("proj", ["obj1", "obj2"])
    assert "FROM aliases" in query
    assert "argMax(digest, created_at)" in query
    assert params == {"project_id": "proj", "object_ids": ["obj1", "obj2"]}


def test_make_resolve_alias_query():
    query, params = make_resolve_alias_query("proj", "obj1", "production")
    assert "FROM aliases" in query
    assert "LIMIT 1" in query
    assert params == {"project_id": "proj", "object_id": "obj1", "alias": "production"}


# --- ObjectMetadataQueryBuilder tag/alias conditions ---


def test_add_tags_condition():
    builder = ObjectMetadataQueryBuilder(project_id="test_project")
    builder.add_tags_condition(["reviewed", "staging"])

    query = builder.conditions_part
    assert "tags" in query
    assert "filter_tags" in query
    assert builder.parameters["filter_tags"] == ["reviewed", "staging"]


def test_add_aliases_condition():
    builder = ObjectMetadataQueryBuilder(project_id="test_project")
    builder.add_aliases_condition(["production", "canary"])

    query = builder.conditions_part
    assert "aliases" in query
    assert "filter_aliases" in query
    assert builder.parameters["filter_aliases"] == ["production", "canary"]


def test_tags_condition_in_full_query():
    """The tag subquery should appear in the full metadata query."""
    builder = ObjectMetadataQueryBuilder(project_id="test_project")
    builder.add_tags_condition(["reviewed"])
    full_query = builder.make_metadata_query()
    assert "filter_tags" in full_query
    assert "tags" in full_query


def test_aliases_condition_in_full_query():
    """The alias subquery should appear in the full metadata query."""
    builder = ObjectMetadataQueryBuilder(project_id="test_project")
    builder.add_aliases_condition(["production"])
    full_query = builder.make_metadata_query()
    assert "filter_aliases" in full_query
    assert "aliases" in full_query
