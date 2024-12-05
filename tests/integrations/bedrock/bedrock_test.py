import json

import boto3
import pytest

import weave
from weave.integrations.bedrock import patch_client

model_id = "anthropic.claude-3-5-sonnet-20240620-v1:0"


system_message = "You are an expert software engineer that knows a lot of programming. You prefer short answers."
messages = [
    {
        "role": "user",
        "content": [
            {
                "text": (
                    "In Bash, how do I list all text files in the current directory "
                    "(excluding subdirectories) that have been modified in the last month?"
                )
            }
        ],
    }
]


def _remove_body_from_response(response):
    if "body" in response:
        response["body"] = None  # Remove the body content
    return response


@pytest.mark.skip_clickhouse_client
@pytest.mark.vcr(
    filter_headers=[
        "authorization",
        "content-type",
        "user-agent",
        "x-amz-date",
        "x-amz-security-token",
        "x-amz-sso_bearer_token",
        "amz-sdk-invocation-id",
    ],
    before_record_response=_remove_body_from_response,
    allowed_hosts=[
        "api.wandb.ai",
        "localhost",
    ],
)
def test_bedrock_converse(client: weave.trace.weave_client.WeaveClient) -> None:
    bedrock_client = boto3.client("bedrock-runtime")
    patch_client(bedrock_client)

    response = bedrock_client.converse(
        modelId=model_id,
        system=[{"text": system_message}],  # it needs a list for some reason
        messages=messages,
        inferenceConfig={"maxTokens": 30},
    )

    # Verify the response structure
    assert response is not None
    assert "output" in response
    assert "message" in response["output"]
    assert "content" in response["output"]["message"]


@pytest.mark.skip_clickhouse_client
@pytest.mark.vcr(
    filter_headers=[
        "authorization",
        "content-type",
        "user-agent",
        "x-amz-date",
        "x-amz-security-token",
        "x-amz-sso_bearer_token",
        "amz-sdk-invocation-id",
    ],
    allowed_hosts=["api.wandb.ai", "localhost"],
)
def test_bedrock_invoke(client: weave.trace.weave_client.WeaveClient) -> None:
    bedrock_client = boto3.client("bedrock-runtime")
    patch_client(bedrock_client)

    body = json.dumps(
        {
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": 30,
            "temperature": 0.7,
            "messages": [{"role": "user", "content": "What is the capital of France?"}],
        }
    )

    response = bedrock_client.invoke_model(
        modelId=model_id,
        body=body,
        contentType="application/json",
        accept="application/json",
    )

    invoke_output = json.loads(response.get("body").read())

    # Verify the response structure
    assert invoke_output is not None
    assert "content" in invoke_output


@pytest.mark.skip_clickhouse_client
@pytest.mark.vcr(
    filter_headers=[
        "authorization",
        "content-type",
        "user-agent",
        "x-amz-date",
        "x-amz-security-token",
        "x-amz-sso_bearer_token",
        "amz-sdk-invocation-id",
    ],
    allowed_hosts=[
        "api.wandb.ai",
        "localhost",
    ],
)
def test_bedrock_converse_stream(client: weave.trace.weave_client.WeaveClient) -> None:
    bedrock_client = boto3.client("bedrock-runtime")
    patch_client(bedrock_client)

    response = bedrock_client.converse_stream(
        modelId=model_id,
        system=[{"text": system_message}],
        messages=messages,
        inferenceConfig={"maxTokens": 30},
    )
    # Access the stream from the response
    stream = response.get('stream')
    assert stream is not None, "Stream not found in response"

    # Accumulate the streamed response
    final_response = None
    for event in stream:
        # Process each event (the accumulator handles this internally)
        final_response = event  # The final event after accumulation

    assert final_response is not None
    # assert "content" in final_response
    # assert len(final_response["content"]) > 0