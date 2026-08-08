"""Tests for Bedrock Nova cross-region inference model-name prefixing."""

from unittest.mock import patch

import pytest

from weave.trace_server import llm_completion as llm_mod
from weave.trace_server import trace_server_interface as tsi


def _nova_inputs(model: str = "amazon.nova-lite-v1:0") -> tsi.CompletionsCreateRequestInputs:
    return tsi.CompletionsCreateRequestInputs(model=model)


@pytest.mark.parametrize(
    "region,expected_prefix",
    [
        ("us-east-1", "us"),
        ("eu-west-1", "eu"),
        ("ap-southeast-1", "apac"),
        ("ap-northeast-1", "apac"),
    ],
)
def test_nova_model_prefix_uses_geography(region, expected_prefix):
    """Nova model names get the Bedrock cross-region inference geography
    prefix. Asia-Pacific regions must map to ``apac``, not ``ap`` (see #7325)."""
    inputs = _nova_inputs()
    with patch.object(
        llm_mod,
        "get_bedrock_credentials",
        return_value=("key", "secret", region),
    ):
        llm_mod._setup_provider_credentials_and_model(inputs, provider="bedrock")

    assert inputs.model == f"bedrock/{expected_prefix}.amazon.nova-lite-v1:0"


def test_non_nova_model_untouched():
    inputs = _nova_inputs(model="anthropic.claude-3-5-sonnet-20240620-v1:0")
    original = inputs.model
    with patch.object(
        llm_mod,
        "get_bedrock_credentials",
        return_value=("key", "secret", "ap-southeast-1"),
    ):
        llm_mod._setup_provider_credentials_and_model(inputs, provider="bedrock")

    assert inputs.model == original
