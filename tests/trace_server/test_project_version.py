import asyncio
import base64
import os
import uuid
from contextlib import contextmanager
from unittest.mock import patch

import pytest

from tests.trace.util import client_is_sqlite
from weave.trace_server.project_version.project_version import ProjectVersionResolver
from weave.trace_server.project_version.providers.clickhouse_provider import (
    ClickHouseProjectVersionProvider,
)
from weave.trace_server.project_version.providers.memory_cache_provider import (
    InMemoryCacheProvider,
)
from weave.trace_server.project_version.types import ProjectVersion, ProjectVersionMode


def make_project_id(name: str) -> str:
    return base64.b64encode(f"test_entity/{name}".encode()).decode()


def insert_call(ch_client, table: str, project_id: str):
    ch_client.command(
        f"""
        INSERT INTO {table} (project_id, id, op_name, started_at, trace_id, parent_id)
        VALUES ('{project_id}', '{uuid.uuid4()}', 'test_op', now(), '{uuid.uuid4()}', '')
        """
    )


@contextmanager
def count_queries(ch_client):
    call_count = 0
    original_query = ch_client.query

    def counting_query(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        return original_query(*args, **kwargs)

    with patch.object(ch_client, "query", side_effect=counting_query):
        yield lambda: call_count


def test_version_resolution_by_table_contents(client, trace_server):
    if client_is_sqlite(client):
        pytest.skip("ClickHouse-only test")

    ch_server = trace_server._internal_trace_server
    resolver = ProjectVersionResolver(ch_client_factory=lambda: ch_server.ch_client)

    empty_proj = make_project_id("empty_project")
    assert resolver.get_project_version_sync(empty_proj) == ProjectVersion.EMPTY_PROJECT

    merged_proj = make_project_id("merged_only")
    insert_call(ch_server.ch_client, "calls_merged", merged_proj)
    assert (
        resolver.get_project_version_sync(merged_proj)
        == ProjectVersion.CALLS_MERGED_VERSION
    )

    complete_proj = make_project_id("complete_only")
    insert_call(ch_server.ch_client, "calls_complete", complete_proj)
    assert (
        resolver.get_project_version_sync(complete_proj)
        == ProjectVersion.CALLS_COMPLETE_VERSION
    )

    both_proj = make_project_id("both_tables")
    insert_call(ch_server.ch_client, "calls_merged", both_proj)
    insert_call(ch_server.ch_client, "calls_complete", both_proj)
    assert (
        resolver.get_project_version_sync(both_proj)
        == ProjectVersion.CALLS_MERGED_VERSION
    )


def test_caching_behavior(client, trace_server):
    if client_is_sqlite(client):
        pytest.skip("ClickHouse-only test")

    ch_server = trace_server._internal_trace_server
    resolver = ProjectVersionResolver(ch_client_factory=lambda: ch_server.ch_client)

    cached_proj = make_project_id("cached_project")
    insert_call(ch_server.ch_client, "calls_complete", cached_proj)

    with count_queries(ch_server.ch_client) as get_count:
        version1 = resolver.get_project_version_sync(cached_proj)
        assert version1 == ProjectVersion.CALLS_COMPLETE_VERSION
        assert get_count() == 1

        version2 = resolver.get_project_version_sync(cached_proj)
        assert version2 == ProjectVersion.CALLS_COMPLETE_VERSION
        assert get_count() == 1

    empty_proj = make_project_id("empty_not_cached")
    with count_queries(ch_server.ch_client) as get_count:
        version1 = resolver.get_project_version_sync(empty_proj)
        assert version1 == ProjectVersion.EMPTY_PROJECT
        assert get_count() == 1

        version2 = resolver.get_project_version_sync(empty_proj)
        assert version2 == ProjectVersion.EMPTY_PROJECT
        assert get_count() == 2


def test_mode_off_and_calls_merged(client, trace_server):
    if client_is_sqlite(client):
        pytest.skip("ClickHouse-only test")

    ch_server = trace_server._internal_trace_server
    resolver = ProjectVersionResolver(ch_client_factory=lambda: ch_server.ch_client)

    project_id = make_project_id("mode_test")
    insert_call(ch_server.ch_client, "calls_complete", project_id)

    resolver._mode = ProjectVersionMode.OFF
    with count_queries(ch_server.ch_client) as get_count:
        version = resolver.get_project_version_sync(project_id)
        assert version == ProjectVersion.CALLS_MERGED_VERSION
        assert get_count() == 0

    resolver._mode = ProjectVersionMode.CALLS_MERGED
    version = resolver.get_project_version_sync(project_id)
    assert version == ProjectVersion.CALLS_MERGED_VERSION

    resolver._mode = ProjectVersionMode.AUTO
    version = resolver.get_project_version_sync(project_id)
    assert version == ProjectVersion.CALLS_COMPLETE_VERSION


def test_mode_calls_merged_read(client, trace_server):
    if client_is_sqlite(client):
        pytest.skip("ClickHouse-only test")

    ch_server = trace_server._internal_trace_server
    resolver = ProjectVersionResolver(ch_client_factory=lambda: ch_server.ch_client)
    resolver._mode = ProjectVersionMode.CALLS_MERGED_READ

    project_id = make_project_id("mode_merged_read")
    insert_call(ch_server.ch_client, "calls_complete", project_id)

    with count_queries(ch_server.ch_client) as get_count:
        read_version = resolver.get_project_version_sync(project_id, is_write=False)
        assert read_version == ProjectVersion.CALLS_MERGED_VERSION
        assert get_count() == 0

    write_version = resolver.get_project_version_sync(project_id, is_write=True)
    assert write_version == ProjectVersion.CALLS_COMPLETE_VERSION


def test_clickhouse_provider_directly(client, trace_server):
    if client_is_sqlite(client):
        pytest.skip("ClickHouse-only test")

    ch_server = trace_server._internal_trace_server
    project_id = make_project_id("provider_direct")
    insert_call(ch_server.ch_client, "calls_merged", project_id)

    provider = ClickHouseProjectVersionProvider(
        ch_client_factory=lambda: ch_server.ch_client
    )
    version = provider.get_project_version_sync(project_id)

    assert version == ProjectVersion.CALLS_MERGED_VERSION


def test_memory_cache_provider():
    cache = InMemoryCacheProvider(maxsize=10)
    project_id = "test-project"

    assert cache.get(project_id) is None

    cache.set(project_id, ProjectVersion.CALLS_COMPLETE_VERSION)
    assert cache.get(project_id) == ProjectVersion.CALLS_COMPLETE_VERSION
    assert cache.get_cache_size() == 1

    cache.clear()
    assert cache.get(project_id) is None
    assert cache.get_cache_size() == 0

    cache_lru = InMemoryCacheProvider(maxsize=2)
    cache_lru.set("proj1", ProjectVersion.CALLS_MERGED_VERSION)
    cache_lru.set("proj2", ProjectVersion.CALLS_COMPLETE_VERSION)
    cache_lru.set("proj3", ProjectVersion.CALLS_COMPLETE_VERSION)

    assert cache_lru.get_cache_size() == 2
    assert cache_lru.get("proj1") is None
    assert cache_lru.get("proj2") == ProjectVersion.CALLS_COMPLETE_VERSION
    assert cache_lru.get("proj3") == ProjectVersion.CALLS_COMPLETE_VERSION


def test_async_and_multiple_projects(client, trace_server):
    if client_is_sqlite(client):
        pytest.skip("ClickHouse-only test")

    ch_server = trace_server._internal_trace_server
    resolver = ProjectVersionResolver(ch_client_factory=lambda: ch_server.ch_client)

    async_proj = make_project_id("async_test")
    insert_call(ch_server.ch_client, "calls_complete", async_proj)

    async def check_async():
        version = await resolver.get_project_version_async(async_proj)
        return version

    version = asyncio.run(check_async())
    assert version == ProjectVersion.CALLS_COMPLETE_VERSION

    project1 = make_project_id("project1")
    project2 = make_project_id("project2")
    insert_call(ch_server.ch_client, "calls_merged", project1)
    insert_call(ch_server.ch_client, "calls_complete", project2)

    version1 = resolver.get_project_version_sync(project1)
    version2 = resolver.get_project_version_sync(project2)

    assert version1 == ProjectVersion.CALLS_MERGED_VERSION
    assert version2 == ProjectVersion.CALLS_COMPLETE_VERSION
    assert resolver._cache.get_cache_size() >= 2


def test_project_version_mode_from_env():
    original_value = os.environ.get("PROJECT_VERSION_MODE")

    try:
        test_cases = [
            ("off", ProjectVersionMode.OFF),
            ("calls_merged", ProjectVersionMode.CALLS_MERGED),
            ("calls_merged_read", ProjectVersionMode.CALLS_MERGED_READ),
            ("auto", ProjectVersionMode.AUTO),
            ("invalid_mode", ProjectVersionMode.AUTO),
        ]

        for env_val, expected_mode in test_cases:
            os.environ["PROJECT_VERSION_MODE"] = env_val
            mode = ProjectVersionMode.from_env()
            assert mode == expected_mode

        if "PROJECT_VERSION_MODE" in os.environ:
            del os.environ["PROJECT_VERSION_MODE"]
        mode = ProjectVersionMode.from_env()
        assert mode == ProjectVersionMode.AUTO

    finally:
        if original_value is not None:
            os.environ["PROJECT_VERSION_MODE"] = original_value
        elif "PROJECT_VERSION_MODE" in os.environ:
            del os.environ["PROJECT_VERSION_MODE"]


def test_global_singleton_resolver(client, trace_server):
    if client_is_sqlite(client):
        pytest.skip("ClickHouse-only test")

    ch_server = trace_server._internal_trace_server

    resolver1 = ProjectVersionResolver.get_global_instance(
        ch_client_factory=lambda: ch_server.ch_client
    )
    resolver2 = ProjectVersionResolver.get_global_instance(
        ch_client_factory=lambda: ch_server.ch_client
    )

    assert resolver1 is resolver2
