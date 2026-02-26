"""Query builder utilities for object tags and aliases.

Provides functions that return (query, parameters) tuples for ClickHouse
tag/alias operations, following the same pattern as
objects_query_builder.make_objects_val_query_and_parameters.
"""

from typing import Any


def make_assert_obj_version_exists_query(
    project_id: str,
    object_id: str,
    digest: str,
) -> tuple[str, dict[str, Any]]:
    """Build a query to check that an object version exists and is not deleted.

    Args:
        project_id: The project ID to filter by.
        object_id: The object ID to check.
        digest: The digest of the object version.

    Returns:
        A tuple of (sql_query, parameters).
    """
    query = """
        SELECT 1
        FROM object_versions
        PREWHERE project_id = {project_id: String}
            AND object_id = {object_id: String}
        WHERE digest = {digest: String}
        GROUP BY project_id, object_id, digest
        HAVING argMax(deleted_at, created_at) IS NULL
        LIMIT 1
    """
    parameters = {
        "project_id": project_id,
        "object_id": object_id,
        "digest": digest,
    }
    return query, parameters


def make_get_tags_query(
    project_id: str,
    object_ids: list[str],
) -> tuple[str, dict[str, Any]]:
    """Build a query to fetch tags for a list of object_ids.

    Args:
        project_id: The project ID to filter by.
        object_ids: List of object IDs to fetch tags for.

    Returns:
        A tuple of (sql_query, parameters).
    """
    query = """
        SELECT object_id, digest, tag
        FROM tags
        PREWHERE project_id = {project_id: String}
            AND object_id IN {object_ids: Array(String)}
        GROUP BY project_id, object_id, digest, tag
        HAVING argMax(deleted_at, created_at) = toDateTime64(0, 3)
    """
    parameters = {
        "project_id": project_id,
        "object_ids": object_ids,
    }
    return query, parameters


def make_get_aliases_query(
    project_id: str,
    object_ids: list[str],
) -> tuple[str, dict[str, Any]]:
    """Build a query to fetch aliases for a list of object_ids.

    Returns rows of (object_id, digest, alias) where digest is the most
    recently assigned digest for each alias.

    Args:
        project_id: The project ID to filter by.
        object_ids: List of object IDs to fetch aliases for.

    Returns:
        A tuple of (sql_query, parameters).
    """
    query = """
        SELECT object_id, argMax(digest, created_at) AS digest, alias
        FROM aliases
        PREWHERE project_id = {project_id: String}
            AND object_id IN {object_ids: Array(String)}
        GROUP BY project_id, object_id, alias
        HAVING argMax(deleted_at, created_at) = toDateTime64(0, 3)
    """
    parameters = {
        "project_id": project_id,
        "object_ids": object_ids,
    }
    return query, parameters


def make_resolve_alias_query(
    project_id: str,
    object_id: str,
    alias: str,
) -> tuple[str, dict[str, Any]]:
    """Build a query to resolve an alias name to its actual digest.

    Args:
        project_id: The project ID to filter by.
        object_id: The object ID the alias belongs to.
        alias: The alias name to resolve.

    Returns:
        A tuple of (sql_query, parameters).
    """
    query = """
        SELECT argMax(digest, created_at) AS digest
        FROM aliases
        PREWHERE project_id = {project_id: String}
            AND object_id = {object_id: String}
        WHERE alias = {alias: String}
        GROUP BY project_id, object_id, alias
        HAVING argMax(deleted_at, created_at) = toDateTime64(0, 3)
        LIMIT 1
    """
    parameters = {
        "project_id": project_id,
        "object_id": object_id,
        "alias": alias,
    }
    return query, parameters
