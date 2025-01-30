import io
import json
from unittest.mock import patch

import boto3
import botocore
import pytest
from moto import mock_aws

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

invoke_prompt = (
    "In Bash, how do I list all text files in the current directory "
    "(excluding subdirectories) that have been modified in the last month?"
)

# Mock responses
MOCK_CONVERSE_RESPONSE = {
    "ResponseMetadata": {
        "RequestId": "917ceb8d-3a0a-4649-b3bb-527494c17a69",
        "HTTPStatusCode": 200,
        "HTTPHeaders": {
            "date": "Fri, 20 Dec 2024 16:44:08 GMT",
            "content-type": "application/json",
            "content-length": "323",
            "connection": "keep-alive",
            "x-amzn-requestid": "917ceb8d-3a0a-4649-b3bb-527494c17a69",
        },
        "RetryAttempts": 0,
    },
    "output": {
        "message": {
            "role": "assistant",
            "content": [
                {
                    "text": "To list all text files in the current directory (excluding subdirectories) "
                    "that have been modified in the last month using Bash, you can use"
                }
            ],
        }
    },
    "stopReason": "max_tokens",
    "usage": {"inputTokens": 40, "outputTokens": 30, "totalTokens": 70},
    "metrics": {"latencyMs": 838},
}

MOCK_STREAM_EVENTS = [
    {"messageStart": {"role": "assistant"}},
    {"contentBlockDelta": {"delta": {"text": "To"}, "contentBlockIndex": 0}},
    {
        "contentBlockDelta": {
            "delta": {"text": " list all text files"},
            "contentBlockIndex": 0,
        }
    },
    {
        "contentBlockDelta": {
            "delta": {"text": " in the current directory"},
            "contentBlockIndex": 0,
        }
    },
    {"contentBlockDelta": {"delta": {"text": " modifie"}, "contentBlockIndex": 0}},
    {
        "contentBlockDelta": {
            "delta": {"text": "d in the last month"},
            "contentBlockIndex": 0,
        }
    },
    {"contentBlockDelta": {"delta": {"text": ", use"}, "contentBlockIndex": 0}},
    {"contentBlockDelta": {"delta": {"text": ":"}, "contentBlockIndex": 0}},
    {"contentBlockDelta": {"delta": {"text": "\n\n```bash"}, "contentBlockIndex": 0}},
    {"contentBlockDelta": {"delta": {"text": "\nfind . -max"}, "contentBlockIndex": 0}},
    {"contentBlockDelta": {"delta": {"text": "depth "}, "contentBlockIndex": 0}},
    {"contentBlockDelta": {"delta": {"text": "1"}, "contentBlockIndex": 0}},
    {"contentBlockStop": {"contentBlockIndex": 0}},
    {"messageStop": {"stopReason": "max_tokens"}},
    {
        "metadata": {
            "usage": {"inputTokens": 55, "outputTokens": 30, "totalTokens": 85},
            "metrics": {"latencyMs": 926},
        }
    },
]

MOCK_INVOKE_RESPONSE = {
    "body": io.BytesIO(
        json.dumps(
            {
                "id": "msg_bdrk_01WpFc3918C93ZG9ZMKVqzCd",
                "type": "message",
                "role": "assistant",
                "model": "claude-3-5-sonnet-20240620",
                "content": [
                    {
                        "type": "text",
                        "text": "To list all text files in the current directory (excluding subdirectories) "
                        "that have been modified in the last month using Bash, you can use",
                    }
                ],
                "stop_reason": "end_turn",
                "stop_sequence": None,
                "usage": {"input_tokens": 40, "output_tokens": 30, "total_tokens": 70},
            }
        ).encode("utf-8")
    ),
    "ContentType": "application/json",
}

# Original botocore _make_api_call function
orig = botocore.client.BaseClient._make_api_call


def mock_converse_make_api_call(self, operation_name, kwarg):
    if operation_name == "Converse":
        return MOCK_CONVERSE_RESPONSE
    elif operation_name == "ConverseStream":

        class MockStream:
            def __iter__(self):
                yield from MOCK_STREAM_EVENTS

        return {"stream": MockStream()}
    return orig(self, operation_name, kwarg)


def mock_invoke_make_api_call(self, operation_name, kwarg):
    if operation_name == "InvokeModel":
        return MOCK_INVOKE_RESPONSE
    return orig(self, operation_name, kwarg)


@pytest.mark.skip_clickhouse_client
@mock_aws
def test_bedrock_converse(client: weave.trace.weave_client.WeaveClient) -> None:
    bedrock_client = boto3.client("bedrock-runtime", region_name="us-east-1")
    patch_client(bedrock_client)

    with patch(
        "botocore.client.BaseClient._make_api_call", new=mock_converse_make_api_call
    ):
        response = bedrock_client.converse(
            modelId=model_id,
            system=[{"text": system_message}],
            messages=messages,
            inferenceConfig={"maxTokens": 30},
        )

        # Existing checks
        assert response is not None
        assert "output" in response
        assert "message" in response["output"]
        assert "content" in response["output"]["message"]

    # Now verify that a trace was captured.
    calls = list(client.calls())
    assert len(calls) == 1, "Expected exactly one trace call"
    call = calls[0]

    assert call.exception is None
    assert call.ended_at is not None

    # Inspect the captured output if desired
    output = call.output

    # Confirm we see the same text as in the mock response
    assert (
        output["output"]["message"]["content"][0]["text"]
        == "To list all text files in the current directory (excluding subdirectories) that have been modified in the last month using Bash, you can use"
    )

    # Check usage in a style similar to mistral tests
    summary = call.summary
    assert summary is not None, "Summary should not be None"
    # We'll reference usage by the model_id
    model_usage = summary["usage"][model_id]
    assert model_usage["requests"] == 1, "Expected exactly one request increment"
    # Map the tokens to pydantic usage fields
    # "inputTokens" -> prompt_tokens, "outputTokens" -> completion_tokens
    assert output["usage"]["inputTokens"] == model_usage["prompt_tokens"] == 40
    assert output["usage"]["outputTokens"] == model_usage["completion_tokens"] == 30
    assert output["usage"]["totalTokens"] == model_usage["total_tokens"] == 70


@pytest.mark.skip_clickhouse_client
@mock_aws
def test_bedrock_converse_stream(client: weave.trace.weave_client.WeaveClient) -> None:
    bedrock_client = boto3.client("bedrock-runtime", region_name="us-east-1")
    patch_client(bedrock_client)

    with patch(
        "botocore.client.BaseClient._make_api_call", new=mock_converse_make_api_call
    ):
        response = bedrock_client.converse_stream(
            modelId=model_id,
            system=[{"text": system_message}],
            messages=messages,
            inferenceConfig={"maxTokens": 30},
        )

        # Existing checks
        stream = response.get("stream")
        assert stream is not None, "Stream not found in response"

        # Accumulate the streamed response
        final_response = ""
        for event in stream:
            if "contentBlockDelta" in event:
                final_response += event["contentBlockDelta"]["delta"]["text"]

        assert final_response is not None

    # Now verify that a trace was captured.
    calls = list(client.calls())
    assert len(calls) == 1, "Expected exactly one trace call for the stream test"
    call = calls[0]

    assert call.exception is None
    assert call.ended_at is not None

    output = call.output
    # For a streaming response, you might confirm final partial text is present
    # in the final output or usage data is recorded

    assert "To list all text files" in output["content"]

    # Check usage in a style similar to mistral tests
    summary = call.summary
    assert summary is not None, "Summary should not be None"
    model_usage = summary["usage"][model_id]
    assert model_usage["requests"] == 1
    assert output["usage"]["inputTokens"] == model_usage["prompt_tokens"] == 55
    assert output["usage"]["outputTokens"] == model_usage["completion_tokens"] == 30
    assert output["usage"]["totalTokens"] == model_usage["total_tokens"] == 85


@pytest.mark.skip_clickhouse_client
@mock_aws
def test_bedrock_invoke(client: weave.trace.weave_client.WeaveClient) -> None:
    bedrock_client = boto3.client("bedrock-runtime", region_name="us-east-1")
    patch_client(bedrock_client)

    with patch(
        "botocore.client.BaseClient._make_api_call", new=mock_invoke_make_api_call
    ):
        # Call the custom op that wraps the bedrock_client.invoke_model call
        body = json.dumps(
            {
                "anthropic_version": "bedrock-2023-05-31",
                "max_tokens": 30,
                "temperature": 0.7,
                "messages": [{"role": "user", "content": invoke_prompt}],
            }
        )

        response = bedrock_client.invoke_model(
            modelId=model_id,
            body=body,
            contentType="application/json",
            accept="application/json",
        )
        response = json.loads(response.get("body").read())
        # Basic assertions on the response
        assert response is not None
        assert "type" in response
        assert response["type"] == "message"
        assert "content" in response
        assert response["content"][0]["text"].startswith(
            "To list all text files in the current directory"
        )

    # Check that a trace was captured
    calls = list(client.calls())
    assert len(calls) == 1, "Expected exactly one trace call for invoke command"
    call = calls[0]
    assert call.exception is None
    assert call.ended_at is not None

    output = call.output
    assert "body" in output
    # Confirm usage in the summary
    summary = call.summary
    print(summary)
    assert summary is not None, "Summary should not be None"
    model_usage = summary["usage"][model_id]
    assert model_usage["requests"] == 1
