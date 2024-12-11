# This is included here for convenience.  Instead of creating a dummy API, we can test
# autopatching against the actual OpenAI API.

from typing import Any

import pytest
from openai import OpenAI

from weave.integrations.openai import openai_sdk
from weave.trace.autopatch import AutopatchSettings, IntegrationSettings, OpSettings


@pytest.mark.skip_clickhouse_client  # TODO:VCR recording does not seem to allow us to make requests to the clickhouse db in non-recording mode
@pytest.mark.vcr(
    filter_headers=["authorization"], allowed_hosts=["api.wandb.ai", "localhost"]
)
def test_disabled_integration_doesnt_patch(client_creator):
    autopatch_settings = AutopatchSettings(
        openai=IntegrationSettings(enabled=False),
    )

    with client_creator(autopatch_settings=autopatch_settings) as client:
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
def test_enabled_integration_patches(client_creator):
    autopatch_settings = AutopatchSettings(
        openai=IntegrationSettings(enabled=True),
    )

    with client_creator(autopatch_settings=autopatch_settings) as client:
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
def test_passthrough_op_kwargs(client_creator):
    def redact_inputs(inputs: dict[str, Any]) -> dict[str, Any]:
        return dict.fromkeys(inputs, "REDACTED")

    autopatch_settings = AutopatchSettings(
        openai=IntegrationSettings(
            op_settings=OpSettings(
                postprocess_inputs=redact_inputs,
            )
        )
    )

    # Explicitly reset the patcher here to pretend like we're starting fresh.  We need
    # to do this because `_openai_patcher` is a global variable that is shared across
    # tests.  If we don't reset it, it will retain the state from the previous test,
    # which can cause this test to fail.
    openai_sdk._openai_patcher = None

    with client_creator(autopatch_settings=autopatch_settings) as client:
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
def test_configuration_with_dicts(client_creator):
    def redact_inputs(inputs: dict[str, Any]) -> dict[str, Any]:
        return dict.fromkeys(inputs, "REDACTED")

    autopatch_settings = {
        "openai": {
            "op_settings": {"postprocess_inputs": redact_inputs},
        }
    }

    openai_sdk._openai_patcher = None

    with client_creator(autopatch_settings=autopatch_settings) as client:
        oaiclient = OpenAI()
        oaiclient.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": "tell me a joke"}],
        )

        calls = list(client.get_calls())
        assert len(calls) == 1

        call = calls[0]
        assert all(v == "REDACTED" for v in call.inputs.values())
