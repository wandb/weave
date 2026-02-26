"""Query builder utilities for object tags and aliases.

Provides functions that return (query, parameters) tuples for ClickHouse
tag/alias operations.  SQLite uses simpler queries built inline.
"""

import datetime


def make_assert_obj_version_exists_query(
    project_id: str,
    object_id: str,
    digest: str,
) -> tuple[str, dict]:
    """Build a query to check that an object version exists and is not deleted."""
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
    object_digests: list[tuple[str, str]],
) -> tuple[str, dict]:
    """Build a query to fetch tags for a list of (object_id, digest) pairs."""
    object_ids = list({od[0] for od in object_digests})
    digests = list({od[1] for od in object_digests})
    query = """
        SELECT object_id, digest, tag
        FROM tags
        PREWHERE project_id = {project_id: String}
            AND object_id IN {object_ids: Array(String)}
        WHERE digest IN {digests: Array(String)}
        GROUP BY project_id, object_id, digest, tag
        HAVING argMax(deleted_at, created_at) = toDateTime64(0, 3)
    """
    parameters = {
        "project_id": project_id,
        "object_ids": object_ids,
        "digests": digests,
    }
    return query, parameters


def make_get_aliases_query(
    project_id: str,
    object_ids: list[str],
) -> tuple[str, dict]:
    """Build a query to fetch aliases for a list of object_ids.

    Returns rows of (object_id, digest, alias) where digest is the most
    recently assigned digest for each alias.
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
) -> tuple[str, dict]:
    """Build a query to resolve an alias name to its actual digest."""
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
