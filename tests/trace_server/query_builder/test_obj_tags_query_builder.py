from collections.abc import Callable

import pytest
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


# --- list queries ---


@pytest.mark.parametrize(
    ("make_query", "expected_query"),
    [
        pytest.param(
            make_list_tags_query,
            """
        SELECT tag
        FROM tags
        PREWHERE project_id = {project_id: String}
        GROUP BY project_id, tag
        HAVING argMax(deleted_at, created_at) = toDateTime64(0, 3)
        ORDER BY tag
    """,
            id="list_tags",
        ),
        pytest.param(
            make_list_aliases_query,
            """
        SELECT alias
        FROM aliases
        PREWHERE project_id = {project_id: String}
        GROUP BY project_id, alias
        HAVING argMax(deleted_at, created_at) = toDateTime64(0, 3)
        ORDER BY alias
    """,
            id="list_aliases",
        ),
    ],
)
def test_make_list_query(
    make_query: Callable[[str], tuple[str, dict]], expected_query: str
) -> None:
    query, params = make_query("proj")
    _assert_sql(expected_query, {"project_id": "proj"}, query, params)


# --- ObjectMetadataQueryBuilder tag/alias conditions ---


@pytest.mark.parametrize(
    ("method_name", "names", "expected_query", "expected_params"),
    [
        pytest.param(
            "add_tags_condition",
            ["reviewed", "staging"],
            """
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
    """,
            {"project_id": "test_project", "filter_tags": ["reviewed", "staging"]},
            id="tags",
        ),
        pytest.param(
            "add_aliases_condition",
            ["production", "canary"],
            """
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
    """,
            {"project_id": "test_project", "filter_aliases": ["production", "canary"]},
            id="aliases",
        ),
        # 'latest' alone routes through the hybrid `is_latest` column: no subquery,
        # no filter_aliases param.
        pytest.param(
            "add_aliases_condition",
            ["latest"],
            """
WHERE ((is_latest = 1)
   AND (deleted_at IS NULL))
    """,
            {"project_id": "test_project"},
            id="aliases_latest_only",
        ),
        # 'latest' plus a real alias ORs the hybrid column with the aliases subquery.
        pytest.param(
            "add_aliases_condition",
            ["latest", "production"],
            """
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
    """,
            {"project_id": "test_project", "filter_aliases": ["production"]},
            id="aliases_with_latest",
        ),
    ],
)
def test_metadata_builder_condition(
    method_name: str,
    names: list[str],
    expected_query: str,
    expected_params: dict,
) -> None:
    builder = ObjectMetadataQueryBuilder(project_id="test_project")
    getattr(builder, method_name)(names)
    _assert_sql(
        expected_query, expected_params, builder.conditions_part, builder.parameters
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
