from __future__ import annotations

from collections.abc import Iterator

import pytest

from tests.trace.in_memory_trace_server import InMemoryTraceServer
from tests.trace_server.conftest import TEST_ENTITY
from weave.trace import weave_client
from weave.trace.context import weave_client_context

TEST_PROJECT = "test-project"


@pytest.fixture
def in_memory_client(zero_stack) -> Iterator[weave_client.WeaveClient]:
    """Install an in-memory global client for client-contract tests.

    EvaluationLogger calls require_weave_client() during construction, scoring,
    and cleanup, so these tests need centralized global-client setup/teardown
    rather than just a local server object.
    """
    server = InMemoryTraceServer()
    client = weave_client.WeaveClient(
        TEST_ENTITY,
        TEST_PROJECT,
        server,
        ensure_project_exists=False,
    )
    weave_client_context.set_weave_client_global(client)
    try:
        yield client
    finally:
        client._flush()
        weave_client_context.set_weave_client_global(None)
        server.close()
