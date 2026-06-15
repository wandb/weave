"""Shared VCR configuration and VCR/ClickHouse isolation for integration tests.

Integration tests replay provider traffic (openai, anthropic, ...) from VCR
cassettes while the weave client simultaneously talks to a real ClickHouse
backend over localhost HTTP. vcrpy was never designed for that concurrency,
so this conftest carries two fixtures that keep the two traffic classes from
corrupting each other. See the fixture docstrings for the exact failure
modes; both were observed as real CI failures (integration tests hitting the
live OpenAI API from inside a record_mode="none" cassette).
"""

from __future__ import annotations

from collections.abc import Generator, Iterator

import pytest
import urllib3.connection
import urllib3.connectionpool
import urllib3.poolmanager

try:
    import httpcore
except ImportError:  # pragma: no cover - httpcore ships with httpx everywhere we test
    httpcore = None

try:
    import vcr.patch as vcr_patch
except ImportError:  # pragma: no cover - vcrpy is a test-group dependency
    vcr_patch = None

try:
    from clickhouse_connect.driver import httpclient as ch_httpclient
    from clickhouse_connect.driver import httputil as ch_httputil
except ImportError:  # pragma: no cover - shards without the trace server deps
    ch_httpclient = None
    ch_httputil = None

# Captured at import time, i.e. before any cassette is active, so these are
# guaranteed to be the real (unpatched) urllib3 connection classes.
_REAL_HTTP_CONNECTION = urllib3.connection.HTTPConnection
_REAL_HTTPS_CONNECTION = urllib3.connection.HTTPSConnection


class _VCRImmuneHTTPPool(urllib3.connectionpool.HTTPConnectionPool):
    """Pool whose connections are always real, even while VCR is patching.

    vcrpy swaps ``HTTPConnectionPool.ConnectionCls`` on the *base* class for
    the duration of a cassette; defining the attribute on a subclass shadows
    that patch permanently.
    """

    ConnectionCls = _REAL_HTTP_CONNECTION


class _VCRImmuneHTTPSPool(urllib3.connectionpool.HTTPSConnectionPool):
    ConnectionCls = _REAL_HTTPS_CONNECTION


_VCR_IMMUNE_POOL_CLASSES = {"http": _VCRImmuneHTTPPool, "https": _VCRImmuneHTTPSPool}


@pytest.fixture
def vcr_config() -> dict[str, object]:
    """VCR passthrough for infra: clickhouse (localhost) and the wandb API bypass cassettes; only provider calls replay."""
    return {"ignore_localhost": True, "ignore_hosts": ["api.wandb.ai"]}


def _pin_real_pools(manager: urllib3.poolmanager.PoolManager) -> None:
    manager.pool_classes_by_scheme = _VCR_IMMUNE_POOL_CLASSES
    # Drop pools created before the pin so they are lazily rebuilt with the
    # immune pool class. clickhouse-connect reconnects transparently.
    manager.clear()


@pytest.fixture(scope="session", autouse=True)
def clickhouse_traffic_bypasses_vcr() -> Generator[None, None, None]:
    """Keep clickhouse-connect's HTTP traffic out of VCR's urllib3 stubs.

    The trace-server backend talks to ClickHouse over localhost HTTP via
    urllib3, including from background flush threads, *while* a cassette is
    active. With ``ignore_localhost`` VCR forwards those requests to the real
    server, but each one still flows through vcrpy's ``VCRConnection``, which
    has two nasty side effects:

    1. ``VCRConnection`` wraps every real send in ``vcr.patch.force_reset()``,
       which globally restores *all* transports (including
       ``httpcore.ConnectionPool.handle_request``) to their unpatched
       originals for the duration of the request. Any provider call running
       concurrently (e.g. an openai/httpx request in the test thread) slips
       past the cassette and hits the live API. On slow CI runners this
       happened on most runs.
    2. At cassette exit, vcrpy's ``ConnectionRemover`` closes VCR connections
       still sitting in connection pools, yanking sockets out from under
       in-flight background ClickHouse inserts ("clickhouse_insert_error"
       teardown failures).

    Pinning the real connection classes onto clickhouse-connect's pool
    managers means CH traffic never enters VCR's stubs at all: no
    ``force_reset`` windows, no VCR-owned connections for the remover to
    close. Provider traffic (openai, google-auth, ...) is unaffected and
    still replays from cassettes.
    """
    if ch_httputil is None:
        yield
        return

    mp = pytest.MonkeyPatch()

    real_get_pool_manager = ch_httputil.get_pool_manager

    def immune_get_pool_manager(*args: object, **kwargs: object):
        manager = real_get_pool_manager(*args, **kwargs)
        _pin_real_pools(manager)
        return manager

    # The module-level singleton predates this fixture; pin it in place.
    _pin_real_pools(ch_httputil._default_pool_manager)
    # httpclient binds get_pool_manager by name at import, so patch both the
    # defining module and the importing module.
    mp.setattr(ch_httputil, "get_pool_manager", immune_get_pool_manager)
    mp.setattr(ch_httpclient, "get_pool_manager", immune_get_pool_manager)

    yield

    mp.undo()


@pytest.fixture(scope="session", autouse=True)
def httpcore_stays_patched_during_vcr_passthrough() -> Generator[None, None, None]:
    """Stop VCR's urllib3 passthrough from unpatching httpx/httpcore.

    ``vcr.patch.force_reset()`` (used by the urllib3/httplib stubs around
    every real passthrough send) restores every transport patch, not just the
    urllib3 ones it actually needs. The httpcore stubs never call
    ``force_reset`` — their passthrough invokes the original function captured
    at import — so dropping the httpcore entries from ``reset_patchers`` is
    safe and removes the window in which a concurrent httpx-based provider
    call (openai, anthropic, ...) could bypass an active cassette and reach
    the live API.

    Defense in depth with ``clickhouse_traffic_bypasses_vcr``: that fixture
    removes the main *source* of passthrough sends; this one makes any
    remaining passthrough (e.g. ``ignore_hosts`` traffic) harmless to
    httpx-based clients.
    """
    if vcr_patch is None or httpcore is None:
        yield
        return

    real_reset_patchers = vcr_patch.reset_patchers

    def reset_patchers_without_httpcore() -> Iterator[object]:
        for patcher in real_reset_patchers():
            # mock.patch.object stores the patch target via `getter`.
            if patcher.getter() in {
                httpcore.ConnectionPool,
                httpcore.AsyncConnectionPool,
            }:
                continue
            yield patcher

    mp = pytest.MonkeyPatch()
    mp.setattr(vcr_patch, "reset_patchers", reset_patchers_without_httpcore)

    yield

    mp.undo()
