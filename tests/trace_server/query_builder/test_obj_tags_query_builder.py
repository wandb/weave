import sqlparse

from weave.trace_server.query_builder.obj_tags_query_builder import (
    make_get_aliases_query,
    make_get_tags_query,
    make_obj_version_exists_query,
    make_resolve_alias_query,
)
from weave.trace_server.query_builder.objects_query_builder import (
    ObjectMetadataQueryBuilder,
)


def _assert_sql(
    actual_query: str,
    actual_params: dict,
    expected_query: str,
    expected_params: dict,
) -> None:
    expected_formatted = sqlparse.format(expected_query, reindent=True)
    actual_formatted = sqlparse.format(actual_query, reindent=True)
    assert expected_formatted == actual_formatted, (
        f"\nExpected:\n{expected_formatted}\n\nGot:\n{actual_formatted}"
    )
    assert expected_params == actual_params, (
        f"\nExpected params: {expected_params}\n\nGot params: {actual_params}"
    )


# --- obj_tags_query_builder functions ---


def test_make_obj_version_exists_query():
    query, params = make_obj_version_exists_query("proj", "obj1", "abc123")
    _assert_sql(
        query,
        params,
        expected_query="""
            SELECT 1
            FROM object_versions
            PREWHERE project_id = {project_id: String}
                AND object_id = {object_id: String}
            WHERE digest = {digest: String}
            GROUP BY project_id, object_id, digest
            HAVING argMax(deleted_at, created_at) IS NULL
            LIMIT 1
        """,
        expected_params={
            "project_id": "proj",
            "object_id": "obj1",
            "digest": "abc123",
        },
    )


def test_make_get_tags_query():
    query, params = make_get_tags_query("proj", ["obj1", "obj2"])
    _assert_sql(
        query,
        params,
        expected_query="""
            SELECT object_id, digest, tag
            FROM tags
            PREWHERE project_id = {project_id: String}
                AND object_id IN {object_ids: Array(String)}
            GROUP BY project_id, object_id, digest, tag
            HAVING argMax(deleted_at, created_at) = toDateTime64(0, 3)
            ORDER BY object_id, digest, tag
        """,
        expected_params={
            "project_id": "proj",
            "object_ids": ["obj1", "obj2"],
        },
    )


def test_make_get_aliases_query():
    query, params = make_get_aliases_query("proj", ["obj1", "obj2"])
    _assert_sql(
        query,
        params,
        expected_query="""
            SELECT object_id, argMax(digest, created_at) AS digest, alias
            FROM aliases
            PREWHERE project_id = {project_id: String}
                AND object_id IN {object_ids: Array(String)}
            GROUP BY project_id, object_id, alias
            HAVING argMax(deleted_at, created_at) = toDateTime64(0, 3)
        """,
        expected_params={
            "project_id": "proj",
            "object_ids": ["obj1", "obj2"],
        },
    )


def test_make_resolve_alias_query():
    query, params = make_resolve_alias_query("proj", "obj1", "production")
    _assert_sql(
        query,
        params,
        expected_query="""
            SELECT argMax(digest, created_at) AS digest
            FROM aliases
            PREWHERE project_id = {project_id: String}
                AND object_id = {object_id: String}
            WHERE alias = {alias: String}
            GROUP BY project_id, object_id, alias
            HAVING argMax(deleted_at, created_at) = toDateTime64(0, 3)
            LIMIT 1
        """,
        expected_params={
            "project_id": "proj",
            "object_id": "obj1",
            "alias": "production",
        },
    )


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
    # Alias filter should be version-specific (include digest)
    assert "main.digest" in query.replace(" ", "").replace("\n", "")


def test_add_aliases_condition_with_latest():
    """Filtering by both 'latest' and a real alias should OR them."""
    builder = ObjectMetadataQueryBuilder(project_id="test_project")
    builder.add_aliases_condition(["latest", "production"])

    query = builder.conditions_part
    assert "is_latest = 1" in query
    assert "filter_aliases" in query
    assert builder.parameters["filter_aliases"] == ["production"]
    # The real alias branch should still filter by digest
    assert "argMax(digest" in query


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
