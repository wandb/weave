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


@pytest.mark.vcr(filter_headers=["authorization"])
def test_notdiamond_quickstart(
    client: WeaveClient,
) -> None:
    from notdiamond import NotDiamond

    api_key = os.environ.get("NOTDIAMOND_API_KEY", "DUMMY_API_KEY")
    nd_client = NotDiamond(api_key=api_key)
    llm_configs = [
        _llm_provider("openai/gpt-4o-mini"),
        _llm_provider("openai/gpt-4o"),
    ]
    nd_client.model_router.select_model(
        llm_providers=llm_configs,
        messages=[{"role": "user", "content": "Hello, world!"}],
        metric="accuracy",
        max_model_depth=4,
        hash_content=False,
    )
    calls = list(client.get_calls(filter=tsi.CallsFilter(trace_roots_only=True)))
    flattened_calls = flattened_calls_to_names(flatten_calls(calls))
    assert len([call for call in flattened_calls if "select_model" in call[0]]) == 1


def _llm_provider(model: str) -> dict:
    provider, model_name = model.split("/", 1)
    return {
        "provider": provider,
        "model": model_name,
        "is_custom": False,
        "context_length": None,
        "input_price": None,
        "output_price": None,
        "latency": None,
    }
