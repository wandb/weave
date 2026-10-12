"""Regression test for the VCR isolation in tests/integrations/conftest.py.

Integration tests replay provider traffic from cassettes while the weave
client concurrently talks to the trace server over localhost HTTP. vcrpy's
``force_reset`` used to open windows in which httpx/httpcore was globally
unpatched, letting provider calls escape an active cassette and hit the live
API (observed as real OpenAI 429s in CI). This test pins the invariant
that prevents that. It lives in the langchain shard because this suite's
combination of streaming LLM calls and heavy backend traffic is what
exposed the race, but the invariant is shard-agnostic.

The test carries a ``vcr`` marker without making any HTTP requests: what it
asserts is the *patching state* while a cassette is active, which is exactly
the state every other vcr-marked test runs under.
"""

import httpcore
import pytest

# The import-time original, i.e. the unpatched httpcore method. Private to
# vcrpy, but referencing it directly is the whole point: it is what
# force_reset() restores, and what a cassette must never be reverted to
# mid-test. If vcrpy renames it, this import fails loudly.
from vcr.patch import _HttpcoreConnectionPool_handle_request, force_reset

from weave.trace.weave_client import WeaveClient


@pytest.mark.vcr
def test_force_reset_keeps_httpcore_patched(client: WeaveClient) -> None:
    """force_reset() must not unpatch httpcore while a cassette is active.

    vcrpy's urllib3 stubs wrap every real passthrough send (e.g. requests to
    an ``ignore_hosts`` host) in ``force_reset()``.
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
