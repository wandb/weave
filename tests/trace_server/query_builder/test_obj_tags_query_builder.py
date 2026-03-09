import sqlparse

from weave.trace_server.query_builder.obj_tags_query_builder import (
    make_get_aliases_query,
    make_get_tags_query,
    make_list_aliases_query,
    make_list_tags_query,
    make_obj_version_exists_query,
    make_resolve_alias_query,
)
from weave.trace_server.query_builder.objects_query_builder import (
    ObjectMetadataQueryBuilder,
)


def _assert_sql(
    expected_query: str,
    expected_params: dict,
    actual_query: str,
    actual_params: dict,
) -> None:
    expected_formatted = sqlparse.format(expected_query, reindent=True).strip()
    actual_formatted = sqlparse.format(actual_query, reindent=True).strip()
    assert expected_formatted == actual_formatted, (
        f"\nExpected:\n{expected_formatted}\n\nGot:\n{actual_formatted}"
    )
    assert expected_params == actual_params, (
        f"\nExpected params: {expected_params}\n\nGot params: {actual_params}"
    )


# --- obj_tags_query_builder functions ---


def test_make_obj_version_exists_query():
    query, params = make_obj_version_exists_query("proj", "obj1", "abc123")

    expected_query = """
        SELECT 1
        FROM object_versions
        PREWHERE project_id = {project_id: String}
            AND object_id = {object_id: String}
        WHERE digest = {digest: String}
        GROUP BY project_id, object_id, digest
        HAVING argMax(deleted_at, created_at) IS NULL
        LIMIT 1
    """
    expected_params = {
        "project_id": "proj",
        "object_id": "obj1",
        "digest": "abc123",
    }

    _assert_sql(expected_query, expected_params, query, params)


def test_make_get_tags_query():
    query, params = make_get_tags_query("proj", ["obj1", "obj2"])

    expected_query = """
        SELECT object_id, digest, tag
        FROM tags
        PREWHERE project_id = {project_id: String}
            AND object_id IN {object_ids: Array(String)}
        GROUP BY project_id, object_id, digest, tag
        HAVING argMax(deleted_at, created_at) = toDateTime64(0, 3)
        ORDER BY object_id, digest, tag
    """
    expected_params = {
        "project_id": "proj",
        "object_ids": ["obj1", "obj2"],
    }

    _assert_sql(expected_query, expected_params, query, params)


def test_make_get_aliases_query():
    query, params = make_get_aliases_query("proj", ["obj1", "obj2"])

    expected_query = """
        SELECT object_id, argMax(digest, created_at) AS digest, alias
        FROM aliases
        PREWHERE project_id = {project_id: String}
            AND object_id IN {object_ids: Array(String)}
        GROUP BY project_id, object_id, alias
        HAVING argMax(deleted_at, created_at) = toDateTime64(0, 3)
    """
    expected_params = {
        "project_id": "proj",
        "object_ids": ["obj1", "obj2"],
    }

    _assert_sql(expected_query, expected_params, query, params)


def test_make_resolve_alias_query():
    query, params = make_resolve_alias_query("proj", "obj1", "production")

    expected_query = """
        SELECT argMax(digest, created_at) AS digest
        FROM aliases
        PREWHERE project_id = {project_id: String}
            AND object_id = {object_id: String}
        WHERE alias = {alias: String}
        GROUP BY project_id, object_id, alias
        HAVING argMax(deleted_at, created_at) = toDateTime64(0, 3)
        LIMIT 1
    """
    expected_params = {
        "project_id": "proj",
        "object_id": "obj1",
        "alias": "production",
    }

    _assert_sql(expected_query, expected_params, query, params)


# --- ObjectMetadataQueryBuilder tag/alias conditions ---


def test_add_tags_condition():
    builder = ObjectMetadataQueryBuilder(project_id="test_project")
    builder.add_tags_condition(["reviewed", "staging"])

    expected_query = """
WHERE (((main.project_id,
         main.object_id,
         main.digest) IN
          (SELECT project_id,
                  object_id,
                  digest
           FROM tags PREWHERE project_id = {project_id: String}
           WHERE tag IN {filter_tags: Array(String)}
           GROUP BY project_id,
                    object_id,
                    digest,
                    tag
           HAVING argMax(deleted_at, created_at) = toDateTime64(0, 3)))
       AND (deleted_at IS NULL))
    """
    expected_params = {
        "project_id": "test_project",
        "filter_tags": ["reviewed", "staging"],
    }

    _assert_sql(
        expected_query, expected_params, builder.conditions_part, builder.parameters
    )


def test_add_aliases_condition():
    builder = ObjectMetadataQueryBuilder(project_id="test_project")
    builder.add_aliases_condition(["production", "canary"])

    expected_query = """
WHERE (((main.project_id,
         main.object_id,
         main.digest) IN
          (SELECT project_id,
                  object_id,
                  argMax(digest, created_at) AS digest
           FROM aliases PREWHERE project_id = {project_id: String}
           WHERE alias IN {filter_aliases: Array(String)}
           GROUP BY project_id,
                    object_id,
                    alias
           HAVING argMax(deleted_at, created_at) = toDateTime64(0, 3)))
       AND (deleted_at IS NULL))
    """
    expected_params = {
        "project_id": "test_project",
        "filter_aliases": ["production", "canary"],
    }

    _assert_sql(
        expected_query, expected_params, builder.conditions_part, builder.parameters
    )


def test_add_aliases_condition_latest_only():
    """Filtering by only 'latest' should produce a simple is_latest = 1 condition."""
    builder = ObjectMetadataQueryBuilder(project_id="test_project")
    builder.add_aliases_condition(["latest"])

    expected_query = """
WHERE ((is_latest = 1)
       AND (deleted_at IS NULL))
    """
    expected_params = {
        "project_id": "test_project",
    }

    _assert_sql(
        expected_query, expected_params, builder.conditions_part, builder.parameters
    )


# --- list queries ---


def test_make_list_tags_query():
    query, params = make_list_tags_query("proj")

    expected_query = """
        SELECT tag
        FROM tags
        PREWHERE project_id = {project_id: String}
        GROUP BY project_id, tag
        HAVING argMax(deleted_at, created_at) = toDateTime64(0, 3)
        ORDER BY tag
    """
    expected_params = {
        "project_id": "proj",
    }

    _assert_sql(expected_query, expected_params, query, params)


def test_make_list_aliases_query():
    query, params = make_list_aliases_query("proj")

    expected_query = """
        SELECT alias
        FROM aliases
        PREWHERE project_id = {project_id: String}
        GROUP BY project_id, alias
        HAVING argMax(deleted_at, created_at) = toDateTime64(0, 3)
        ORDER BY alias
    """
    expected_params = {
        "project_id": "proj",
    }

    _assert_sql(expected_query, expected_params, query, params)


def test_add_aliases_condition_with_latest():
    """Filtering by both 'latest' and a real alias should OR them."""
    builder = ObjectMetadataQueryBuilder(project_id="test_project")
    builder.add_aliases_condition(["latest", "production"])

    expected_query = """
WHERE (((is_latest = 1
         OR (main.project_id,
             main.object_id,
             main.digest) IN
           (SELECT project_id,
                   object_id,
                   argMax(digest, created_at) AS digest
            FROM aliases PREWHERE project_id = {project_id: String}
            WHERE alias IN {filter_aliases: Array(String)}
            GROUP BY project_id,
                     object_id,
                     alias
            HAVING argMax(deleted_at, created_at) = toDateTime64(0, 3))))
       AND (deleted_at IS NULL))
    """
    expected_params = {
        "project_id": "test_project",
        "filter_aliases": ["production"],
    }

    _assert_sql(
        expected_query, expected_params, builder.conditions_part, builder.parameters
    )
