import os
from collections.abc import Generator

import pytest

from weave.integrations.integration_utilities import (
    flatten_calls,
    flattened_calls_to_names,
)
from weave.integrations.notdiamond.tracing import get_notdiamond_patcher
from weave.trace.weave_client import WeaveClient
from weave.trace_server import trace_server_interface as tsi


@pytest.fixture(autouse=True)
def patch_notdiamond() -> Generator[None, None, None]:
    """Patch NotDiamond for all tests in this file."""
    patcher = get_notdiamond_patcher()
    patcher.attempt_patch()
    yield
    patcher.undo_patch()


@pytest.mark.skip_clickhouse_client
@pytest.mark.vcr(filter_headers=["authorization"])
def test_notdiamond_quickstart(
    client: WeaveClient,
) -> None:
    from notdiamond import LLMConfig, NotDiamond

    api_key = os.environ.get("NOTDIAMOND_API_KEY", "DUMMY_API_KEY")
    nd_client = NotDiamond(api_key=api_key)
    llm_configs = [
        LLMConfig.from_string("openai/gpt-4o-mini"),
        LLMConfig.from_string("openai/gpt-4o"),
    ]
    _, results = nd_client.model_select(
        model=llm_configs, messages=[{"role": "user", "content": "Hello, world!"}]
    )
    calls = list(client.get_calls(filter=tsi.CallsFilter(trace_roots_only=True)))
    flattened_calls = flattened_calls_to_names(flatten_calls(calls))
    assert len([call for call in flattened_calls if "model_select" in call[0]]) == 1
