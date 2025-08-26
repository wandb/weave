# This tests the explicit patching mechanism for OpenAI

from typing import Any

import pytest
from openai import OpenAI

import weave
from weave.integrations.openai import openai_sdk
from weave.trace.autopatch import IntegrationSettings, OpSettings


@pytest.mark.skip_clickhouse_client  # TODO:VCR recording does not seem to allow us to make requests to the clickhouse db in non-recording mode
@pytest.mark.vcr(
    filter_headers=["authorization"], allowed_hosts=["api.wandb.ai", "localhost"]
)
def test_no_patch_no_trace(client_creator):
    """Test that without explicit patching, OpenAI calls are not traced."""
    with client_creator() as client:
        oaiclient = OpenAI()
        oaiclient.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": "tell me a joke"}],
        )

        calls = list(client.get_calls())
        assert len(calls) == 0


@pytest.mark.skip_clickhouse_client  # TODO:VCR recording does not seem to allow us to make requests to the clickhouse db in non-recording mode
@pytest.mark.vcr(
    filter_headers=["authorization"], allowed_hosts=["api.wandb.ai", "localhost"]
)
def test_explicit_patch_traces(client_creator):
    """Test that explicit patching enables OpenAI tracing."""
    with client_creator() as client:
        # Explicitly patch OpenAI
        weave.patch_openai()
        
        oaiclient = OpenAI()
        oaiclient.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": "tell me a joke"}],
        )

        calls = list(client.get_calls())
        assert len(calls) == 1


@pytest.mark.skip_clickhouse_client  # TODO:VCR recording does not seem to allow us to make requests to the clickhouse db in non-recording mode
@pytest.mark.vcr(
    filter_headers=["authorization"], allowed_hosts=["api.wandb.ai", "localhost"]
)
def test_explicit_patch_with_settings(client_creator):
    """Test explicit patching with custom settings."""
    def redact_inputs(inputs: dict[str, Any]) -> dict[str, Any]:
        return dict.fromkeys(inputs, "REDACTED")

    # Explicitly reset the patcher here to pretend like we're starting fresh.  We need
    # to do this because `_openai_patcher` is a global variable that is shared across
    # tests.  If we don't reset it, it will retain the state from the previous test,
    # which can cause this test to fail.
    openai_sdk._openai_patcher = None

    with client_creator() as client:
        # Patch with custom settings
        settings = IntegrationSettings(
            op_settings=OpSettings(
                postprocess_inputs=redact_inputs,
            )
        )
        weave.patch_openai(settings)
        
        oaiclient = OpenAI()
        oaiclient.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": "tell me a joke"}],
        )

        calls = list(client.get_calls())
        assert len(calls) == 1

        call = calls[0]
        assert all(v == "REDACTED" for v in call.inputs.values())


@pytest.mark.skip_clickhouse_client  # TODO:VCR recording does not seem to allow us to make requests to the clickhouse db in non-recording mode
@pytest.mark.vcr(
    filter_headers=["authorization"], allowed_hosts=["api.wandb.ai", "localhost"]
)
def test_multiple_explicit_patches(client_creator):
    """Test that multiple integrations can be explicitly patched independently."""
    with client_creator() as client:
        # Patch only OpenAI, not other integrations
        weave.patch_openai()
        # Could also do: weave.patch_anthropic(), weave.patch_mistral(), etc.
        
        oaiclient = OpenAI()
        oaiclient.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": "tell me a joke"}],
        )

        calls = list(client.get_calls())
        assert len(calls) == 1
        assert "openai" in calls[0].op_name.lower()