"""Regression tests for the VCR/ClickHouse isolation in tests/integrations/conftest.py.

Integration tests replay provider traffic from cassettes while the weave
client concurrently talks to ClickHouse over localhost HTTP. vcrpy's
``force_reset`` used to open windows in which httpx/httpcore was globally
unpatched, letting provider calls escape an active cassette and hit the live
API (observed as real OpenAI 429s in CI). These tests pin the two invariants
that prevent that. They live in the langchain shard because this suite's
combination of streaming LLM calls and heavy ClickHouse traffic is what
exposed the race, but the invariants are shard-agnostic.

The tests carry a ``vcr`` marker without making any HTTP requests: what they
assert is the *patching state* while a cassette is active, which is exactly
the state every other vcr-marked test runs under.
"""

import httpcore
import pytest
import urllib3.connectionpool
from clickhouse_connect.driver import httputil as ch_httputil

# The import-time original, i.e. the unpatched httpcore method. Private to
# vcrpy, but referencing it directly is the whole point: it is what
# force_reset() restores, and what a cassette must never be reverted to
# mid-test. If vcrpy renames it, this import fails loudly.
from vcr.patch import _HttpcoreConnectionPool_handle_request, force_reset

from weave.trace.weave_client import WeaveClient

VCR_MODULE_PREFIX = "vcr."


@pytest.mark.vcr
def test_force_reset_keeps_httpcore_patched(client: WeaveClient) -> None:
    """force_reset() must not unpatch httpcore while a cassette is active.

    vcrpy's urllib3 stubs wrap every real passthrough send (e.g. the weave
    client's ignored-localhost ClickHouse requests) in ``force_reset()``.
    Without the ``reset_patchers`` filter installed by
    tests/integrations/conftest.py, that window restores the unpatched
    httpcore transport, and any concurrent httpx-based provider call bypasses
    the cassette and reaches the live API.
    """
    patched = httpcore.ConnectionPool.handle_request
    # Sanity: the cassette from our vcr marker is actually patching httpcore.
    assert patched is not _HttpcoreConnectionPool_handle_request

    with force_reset():
        assert httpcore.ConnectionPool.handle_request is patched


@pytest.mark.vcr
def test_clickhouse_pools_bypass_vcr(client: WeaveClient) -> None:
    """clickhouse-connect pools must create real connections under a cassette.

    If ClickHouse traffic flows through vcrpy's ``VCRConnection``, every
    request opens a ``force_reset()`` unpatch window and cassette exit closes
    pooled connections out from under in-flight background inserts.
    tests/integrations/conftest.py pins the real urllib3 connection classes
    onto clickhouse-connect's pool managers to keep its traffic out of VCR.
    """
    # Sanity: the cassette is actively patching urllib3's base pool class, so
    # an unpinned pool would hand out VCR connection classes here.
    base_connection_cls = urllib3.connectionpool.HTTPConnectionPool.ConnectionCls
    assert base_connection_cls.__module__.startswith(VCR_MODULE_PREFIX)

    manager = ch_httputil.default_pool_manager()
    pool = manager.connection_from_host("localhost", 8123, scheme="http")
    assert not pool.ConnectionCls.__module__.startswith(VCR_MODULE_PREFIX)
