"""Unit tests for Bedrock inference-profile ARN → cost model id mapping."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from weave.integrations.bedrock.bedrock_sdk import (
    extract_model_name_from_inference_profile_arn,
)


def test_system_defined_profile_arn_keeps_profile_id() -> None:
    """System-defined ARNs already end with the cost-table key; do not strip us./global."""
    arn = (
        "arn:aws:bedrock:us-east-1:123456789012:inference-profile/"
        "us.openai.gpt-6-astra"
    )
    assert extract_model_name_from_inference_profile_arn(arn) == "us.openai.gpt-6-astra"

    global_arn = (
        "arn:aws:bedrock:us-east-1:123456789012:inference-profile/"
        "global.openai.gpt-6-astra"
    )
    assert (
        extract_model_name_from_inference_profile_arn(global_arn)
        == "global.openai.gpt-6-astra"
    )


def test_system_defined_profile_arn_skips_get_inference_profile() -> None:
    arn = (
        "arn:aws:bedrock:us-east-1:123456789012:inference-profile/"
        "us.anthropic.claude-opus-5"
    )
    with patch(
        "weave.integrations.bedrock.bedrock_sdk.boto3.client"
    ) as client_factory:
        assert (
            extract_model_name_from_inference_profile_arn(arn)
            == "us.anthropic.claude-opus-5"
        )
        client_factory.assert_not_called()


def test_application_inference_profile_uses_lookup() -> None:
    arn = (
        "arn:aws:bedrock:us-east-1:123456789012:application-inference-profile/"
        "my-app-profile"
    )
    fake_client = MagicMock()
    fake_client.get_inference_profile.return_value = {
        "models": [
            {
                "modelArn": (
                    "arn:aws:bedrock:us-east-1::foundation-model/"
                    "anthropic.claude-opus-5"
                )
            }
        ]
    }
    with patch(
        "weave.integrations.bedrock.bedrock_sdk.boto3.client",
        return_value=fake_client,
    ):
        assert (
            extract_model_name_from_inference_profile_arn(arn)
            == "anthropic.claude-opus-5"
        )
    fake_client.get_inference_profile.assert_called_once_with(
        inferenceProfileIdentifier="my-app-profile"
    )
