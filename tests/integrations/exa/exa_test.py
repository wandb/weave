import os
from collections.abc import Generator

import pytest
from exa_py import Exa

import weave
from weave.integrations.exa.exa_sdk import get_exa_patcher


@pytest.fixture()
def patch_exa() -> Generator[None, None, None]:
    patcher = get_exa_patcher()
    patcher.attempt_patch()
    yield
    patcher.undo_patch()


@pytest.mark.skip_clickhouse_client
@pytest.mark.vcr(
    filter_headers=["authorization", "x-api-key"],
    allowed_hosts=["api.wandb.ai", "api.exa.ai", "localhost"],
)
def test_search(
    client: weave.trace.weave_client.WeaveClient,
    patch_exa: None,
) -> None:
    """Test that Exa.search API response is correctly logged in Weave."""
    api_key = os.environ.get("EXA_API_KEY", "DUMMY_API_KEY")

    # Initialize Exa client and perform search
    exa = Exa(api_key)
    api_response = exa.search(query="Latest developments in AI safety", num_results=3)

    # Get the traced call
    calls = list(client.calls())
    assert len(calls) == 1
    call = calls[0]

    # Verify the call completed successfully
    assert call.exception is None and call.ended_at is not None

    # Verify the output in Weave matches the API response
    output = call.output
    assert output is not None
    assert len(output.results) == len(api_response.results)

    # Check that URLs exist and are properly formatted
    for result in output.results:
        assert hasattr(result, "url")
        assert result.url is not None
        assert result.url.startswith("http")

    # Verify cost tracking works correctly
    if hasattr(api_response, "cost_dollars"):
        assert hasattr(output, "cost_dollars")
        assert output.cost_dollars.total == api_response.cost_dollars.total

        # Check cost is in the summary
        assert "usage" in call.summary
        assert "exa" in call.summary["usage"]
        assert call.summary["usage"]["exa"]["prompt_token_cost"] == float(
            output.cost_dollars.total
        )

    # Verify operation name
    assert "Exa.search" in call.op_name


@pytest.mark.skip_clickhouse_client
@pytest.mark.vcr(
    filter_headers=["authorization", "x-api-key"],
    allowed_hosts=["api.wandb.ai", "api.exa.ai", "localhost"],
)
def test_search_and_contents(
    client: weave.trace.weave_client.WeaveClient,
    patch_exa: None,
) -> None:
    """Test that Exa.search_and_contents API response is correctly logged in Weave."""
    api_key = os.environ.get("EXA_API_KEY", "DUMMY_API_KEY")

    # Initialize Exa client and perform search with contents
    exa = Exa(api_key)
    api_response = exa.search_and_contents(
        query="Latest developments in AI safety", text=True, type="auto", num_results=5
    )

    # Get the traced call
    calls = list(client.calls())
    assert len(calls) == 1
    call = calls[0]

    # Verify the call completed successfully
    assert call.exception is None and call.ended_at is not None

    # Verify the output in Weave matches the API response
    output = call.output
    assert output is not None
    assert len(output.results) == len(api_response.results)

    # Check that text content is present in the results
    for result in output.results:
        assert hasattr(result, "url")
        assert result.url is not None
        assert result.url.startswith("http")

        assert hasattr(result, "text")
        assert result.text is not None
        assert len(result.text) > 0

    # Verify cost tracking works correctly
    if hasattr(api_response, "cost_dollars"):
        assert hasattr(output, "cost_dollars")
        assert output.cost_dollars.total == api_response.cost_dollars.total

        # Check cost is in the summary
        assert "usage" in call.summary
        assert "exa" in call.summary["usage"]
        assert call.summary["usage"]["exa"]["prompt_token_cost"] == float(
            output.cost_dollars.total
        )

    # Verify operation name
    assert "Exa.search_and_contents" in call.op_name
