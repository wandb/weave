"""Shared VCR configuration and VCR isolation for integration tests.

Integration tests replay provider traffic (openai, anthropic, ...) from VCR
cassettes while the weave client simultaneously talks to the trace server
over localhost HTTP. vcrpy was never designed for that concurrency, so this
conftest carries a fixture that keeps the two traffic classes from
corrupting each other. See the fixture docstring for the exact failure mode;
it was observed as a real CI failure (integration tests hitting the live
OpenAI API from inside a record_mode="none" cassette).
"""

from __future__ import annotations

from collections.abc import Callable, Generator, Iterator

import pytest

try:
    import httpcore
    from httpcore._models import ByteStream
except ImportError:  # pragma: no cover - httpcore ships with httpx everywhere we test
    httpcore = None

try:
    import vcr.patch as vcr_patch
    import vcr.stubs.httpcore_stubs as vcr_httpcore_stubs
except ImportError:  # pragma: no cover - vcrpy is a test-group dependency
    vcr_patch = None
    vcr_httpcore_stubs = None


@pytest.fixture
def vcr_config() -> dict[str, object]:
    """VCR passthrough for infra: the trace server (localhost) and the wandb API bypass cassettes; only provider calls replay."""
    return {"ignore_localhost": True, "ignore_hosts": ["api.wandb.ai"]}


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

    This makes any passthrough send (e.g. ``ignore_hosts`` traffic) harmless
    to httpx-based clients.
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


@pytest.fixture(scope="session", autouse=True)
def vcr_passthrough_releases_pooled_connections() -> Generator[None, None, None]:
    """Give each passed-through request's connection back to the pool.

    vcrpy 8.1's httpcore stub reads a passed-through response and replaces its
    stream without closing it, so the connection is never released (vcrpy 8.2
    closes it, kevin1024/vcrpy#972). The generated client's pool holds 100
    connections, so the 101st trace server request in a cassette test waits
    for one until it times out; the hand-written client's pool has no limit.
    """
    if vcr_httpcore_stubs is None or httpcore is None:
        yield
        return

    real_vcr_handle_request = vcr_httpcore_stubs._vcr_handle_request

    def vcr_handle_request_and_release(
        cassette: object,
        real_handle_request: Callable[..., httpcore.Response],
        pool: httpcore.ConnectionPool,
        real_request: httpcore.Request,
    ) -> httpcore.Response:
        def send_and_release(
            pool: httpcore.ConnectionPool, request: httpcore.Request
        ) -> httpcore.Response:
            response = real_handle_request(pool, request)
            content = b"".join(response.stream)
            response.stream.close()
            response.stream = ByteStream(content)
            return response

        return real_vcr_handle_request(cassette, send_and_release, pool, real_request)

    mp = pytest.MonkeyPatch()
    mp.setattr(
        vcr_httpcore_stubs, "_vcr_handle_request", vcr_handle_request_and_release
    )

    yield

    mp.undo()
