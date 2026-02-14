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
inference_profile_id = "arn:aws:bedrock:us-east-1::foundation-model/anthropic.claude-3-5-sonnet-20240620-v1:0"

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

# Mock response for apply_guardrail
MOCK_APPLY_GUARDRAIL_RESPONSE = {
    "ResponseMetadata": {
        "RequestId": "a1b2c3d4-e5f6-7890-a1b2-c3d4e5f67890",
        "HTTPStatusCode": 200,
        "HTTPHeaders": {
            "date": "Fri, 20 Dec 2024 16:44:08 GMT",
            "content-type": "application/json",
            "content-length": "456",
            "connection": "keep-alive",
            "x-amzn-requestid": "a1b2c3d4-e5f6-7890-a1b2-c3d4e5f67890",
        },
        "RetryAttempts": 0,
    },
    "action": "ALLOW",  # or "GUARDRAIL_INTERVENED"
    "outputs": [
        {
            "text": "I can provide general information about retirement planning. Consider diversifying your investments across stocks, bonds, and other assets based on your risk tolerance and time horizon. Consult with a financial advisor for personalized advice."
        }
    ],
    "assessments": [
        {
            "topicPolicy": {
                "topics": [
                    {"name": "Financial advice", "type": "FILTERED", "confidence": 0.95}
                ]
            }
        }
    ],
    "usage": {"inputTokens": 25, "outputTokens": 45, "totalTokens": 70},
}

# Mock response for apply_guardrail with intervention
MOCK_APPLY_GUARDRAIL_INTERVENTION_RESPONSE = {
    "ResponseMetadata": {
        "RequestId": "a1b2c3d4-e5f6-7890-a1b2-c3d4e5f67890",
        "HTTPStatusCode": 200,
        "HTTPHeaders": {
            "date": "Fri, 20 Dec 2024 16:44:08 GMT",
            "content-type": "application/json",
            "content-length": "456",
            "connection": "keep-alive",
            "x-amzn-requestid": "a1b2c3d4-e5f6-7890-a1b2-c3d4e5f67890",
        },
        "RetryAttempts": 0,
    },
    "action": "GUARDRAIL_INTERVENED",
    "outputs": [
        {
            "text": "I cannot provide specific investment advice. Please consult with a qualified financial advisor for personalized retirement planning guidance."
        }
    ],
    "assessments": [
        {
            "topicPolicy": {
                "topics": [
                    {"name": "Financial advice", "type": "BLOCKED", "confidence": 0.98}
                ]
            }
        }
    ],
    "usage": {"inputTokens": 25, "outputTokens": 30, "totalTokens": 55},
}

# Mock streaming events for invoke_model_with_response_stream (Anthropic Claude format)
# These simulate the SSE events from Anthropic Claude via Bedrock's invoke_model_with_response_stream
MOCK_INVOKE_STREAM_EVENTS = [
    {
        "chunk": {
            "bytes": json.dumps(
                {
                    "type": "message_start",
                    "message": {
                        "id": "msg_bdrk_stream_01",
                        "type": "message",
                        "role": "assistant",
                        "content": [],
                        "model": "claude-3-5-sonnet-20240620",
                        "stop_reason": None,
                        "stop_sequence": None,
                        "usage": {"input_tokens": 40, "output_tokens": 1},
                    },
                }
            ).encode("utf-8")
        }
    },
    {
        "chunk": {
            "bytes": json.dumps(
                {
                    "type": "content_block_start",
                    "index": 0,
                    "content_block": {"type": "text", "text": ""},
                }
            ).encode("utf-8")
        }
    },
    {
        "chunk": {
            "bytes": json.dumps(
                {
                    "type": "content_block_delta",
                    "index": 0,
                    "delta": {"type": "text_delta", "text": "To list "},
                }
            ).encode("utf-8")
        }
    },
    {
        "chunk": {
            "bytes": json.dumps(
                {
                    "type": "content_block_delta",
                    "index": 0,
                    "delta": {"type": "text_delta", "text": "all text files"},
                }
            ).encode("utf-8")
        }
    },
    {
        "chunk": {
            "bytes": json.dumps(
                {
                    "type": "content_block_delta",
                    "index": 0,
                    "delta": {
                        "type": "text_delta",
                        "text": " in the current directory",
                    },
                }
            ).encode("utf-8")
        }
    },
    {
        "chunk": {
            "bytes": json.dumps({"type": "content_block_stop", "index": 0}).encode(
                "utf-8"
            )
        }
    },
    {
        "chunk": {
            "bytes": json.dumps(
                {
                    "type": "message_delta",
                    "delta": {"stop_reason": "end_turn", "stop_sequence": None},
                    "usage": {"output_tokens": 30},
                }
            ).encode("utf-8")
        }
    },
    {"chunk": {"bytes": json.dumps({"type": "message_stop"}).encode("utf-8")}},
]


# Mock response for bedrock-agent-runtime invoke_agent
MOCK_INVOKE_AGENT_EVENTS = [
    {"chunk": {"bytes": b"Hello! I'm here to help you. How can I assist you today?"}},
    {
        "trace": {
            "trace": {
                "sessionId": "test-session",
                "trace": {
                    "orchestrationTrace": {
                        "invocationInput": {
                            "invocationType": "ACTION",
                            "actionInvocationType": "RESULT",
                        }
                    }
                },
            }
        }
    },
]

MOCK_INVOKE_AGENT_RESPONSE = {
    "ResponseMetadata": {
        "RequestId": "test-request-id",
        "HTTPStatusCode": 200,
        "HTTPHeaders": {
            "date": "Fri, 20 Dec 2024 16:44:08 GMT",
            "content-type": "application/vnd.amazon.eventstream",
            "transfer-encoding": "chunked",
            "connection": "keep-alive",
            "x-amzn-requestid": "test-request-id",
            "x-amz-bedrock-agent-session-id": "test-session",
            "x-amzn-bedrock-agent-content-type": "application/json",
        },
        "RetryAttempts": 0,
    },
    "completion": MOCK_INVOKE_AGENT_EVENTS,
    "contentType": "application/json",
    "sessionId": "test-session",
}

# Original botocore _make_api_call function
orig = botocore.client.BaseClient._make_api_call


def mock_converse_make_api_call(self, operation_name: str, api_params: dict) -> dict:
    if operation_name == "Converse":
        return MOCK_CONVERSE_RESPONSE
    elif operation_name == "ConverseStream":

        class MockStream:
            def __iter__(self):
                yield from MOCK_STREAM_EVENTS

        return {"stream": MockStream()}
    return orig(self, operation_name, api_params)


def mock_invoke_make_api_call(self, operation_name: str, api_params: dict) -> dict:
    if operation_name == "InvokeModel":
        return MOCK_INVOKE_RESPONSE
    return orig(self, operation_name, api_params)


def mock_invoke_stream_make_api_call(
    self, operation_name: str, api_params: dict
) -> dict:
    if operation_name == "InvokeModelWithResponseStream":

        class MockStreamBody:
            def __iter__(self):
                yield from MOCK_INVOKE_STREAM_EVENTS

        return {"body": MockStreamBody(), "contentType": "application/json"}
    return orig(self, operation_name, api_params)


def mock_invoke_stream_exception_make_api_call(
    self, operation_name: str, api_params: dict
) -> dict:
    if operation_name == "InvokeModelWithResponseStream":
        from botocore.exceptions import ClientError

        raise ClientError(
            error_response={
                "Error": {
                    "Code": "ValidationException",
                    "Message": "The provided model identifier is invalid.",
                }
            },
            operation_name="InvokeModelWithResponseStream",
        )
    return orig(self, operation_name, api_params)


def mock_apply_guardrail_make_api_call(
    self, operation_name: str, api_params: dict
) -> dict:
    if operation_name == "ApplyGuardrail":
        # Check if we should return the intervention response based on the content
        content = api_params.get("content", [])
        if content and isinstance(content, list) and len(content) > 0:
            text_content = content[0].get("text", {}).get("text", "")
            if "specific investment" in text_content.lower():
                return MOCK_APPLY_GUARDRAIL_INTERVENTION_RESPONSE
        return MOCK_APPLY_GUARDRAIL_RESPONSE
    return orig(self, operation_name, api_params)


def mock_invoke_exception_make_api_call(
    self, operation_name: str, api_params: dict
) -> dict:
    if operation_name == "InvokeModel":
        # Simulate a ValidationException for invalid model ID
        from botocore.exceptions import ClientError

        raise ClientError(
            error_response={
                "Error": {
                    "Code": "ValidationException",
                    "Message": "The provided model identifier is invalid.",
                }
            },
            operation_name="InvokeModel",
        )
    return orig(self, operation_name, api_params)


def mock_invoke_agent_make_api_call(
    self, operation_name: str, api_params: dict
) -> dict:
    if operation_name == "InvokeAgent":
        return MOCK_INVOKE_AGENT_RESPONSE
    return orig(self, operation_name, api_params)


@pytest.mark.skip_clickhouse_client
@mock_aws
@pytest.mark.parametrize("model_identifier", [model_id, inference_profile_id])
def test_bedrock_converse(
    client: weave.trace.weave_client.WeaveClient, model_identifier: str
) -> None:
    bedrock_client = boto3.client("bedrock-runtime", region_name="us-east-1")
    patch_client(bedrock_client)

    with patch(
        "botocore.client.BaseClient._make_api_call", new=mock_converse_make_api_call
    ):
        response = bedrock_client.converse(
            modelId=model_identifier,
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
    calls = list(client.get_calls())
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
    # We'll reference usage by the model_id, even if we used an inference profile
    model_usage = summary["usage"][model_id]
    assert model_usage["requests"] == 1, "Expected exactly one request increment"
    # Map the tokens to pydantic usage fields
    # "inputTokens" -> prompt_tokens, "outputTokens" -> completion_tokens
    assert output["usage"]["inputTokens"] == model_usage["prompt_tokens"] == 40
    assert output["usage"]["outputTokens"] == model_usage["completion_tokens"] == 30
    assert output["usage"]["totalTokens"] == model_usage["total_tokens"] == 70


@pytest.mark.skip_clickhouse_client
@mock_aws
@pytest.mark.parametrize("model_identifier", [model_id, inference_profile_id])
def test_bedrock_converse_stream(
    client: weave.trace.weave_client.WeaveClient, model_identifier: str
) -> None:
    bedrock_client = boto3.client("bedrock-runtime", region_name="us-east-1")
    patch_client(bedrock_client)

    with patch(
        "botocore.client.BaseClient._make_api_call", new=mock_converse_make_api_call
    ):
        response = bedrock_client.converse_stream(
            modelId=model_identifier,
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
    calls = client.get_calls()
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
    calls = list(client.get_calls())
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


@pytest.mark.skip_clickhouse_client
@mock_aws
def test_bedrock_apply_guardrail(client: weave.trace.weave_client.WeaveClient) -> None:
    from weave.scorers.bedrock_guardrails import BedrockGuardrailScorer

    scorer = BedrockGuardrailScorer(
        guardrail_id="test-guardrail-id",
        guardrail_version="DRAFT",
        source="OUTPUT",
        bedrock_runtime_kwargs={"region_name": "us-east-1"},
    )

    # Test with content that should pass the guardrail
    with patch(
        "botocore.client.BaseClient._make_api_call",
        new=mock_apply_guardrail_make_api_call,
    ):
        result = scorer.score(
            output="How should I think about retirement planning in general?"
        )

        # Verify the result
        assert result.passed is True
        assert "modified_output" in result.metadata
        assert "usage" in result.metadata
        assert "assessments" in result.metadata

        # Check that the modified output matches our mock
        assert (
            result.metadata["modified_output"]
            == MOCK_APPLY_GUARDRAIL_RESPONSE["outputs"][0]["text"]
        )

        # Check usage data
        assert result.metadata["usage"]["inputTokens"] == 25
        assert result.metadata["usage"]["outputTokens"] == 45
        assert result.metadata["usage"]["totalTokens"] == 70

    # Now verify that a trace was captured
    calls = list(client.get_calls())
    assert len(calls) >= 1, "Expected at least one trace call"
    # Find the score call
    score_calls = [call for call in calls if "score" in call._op_name]
    assert len(score_calls) == 1, "Expected exactly one score call"
    call = score_calls[0]

    assert call.exception is None
    assert call.ended_at is not None

    # Test with content that should trigger guardrail intervention
    with patch(
        "botocore.client.BaseClient._make_api_call",
        new=mock_apply_guardrail_make_api_call,
    ):
        result = scorer.score(
            output="Give me specific investment advice for my retirement to generate $5,000 monthly."
        )

        # Verify the result shows intervention
        assert result.passed is False
        assert "modified_output" in result.metadata
        assert "usage" in result.metadata
        assert "assessments" in result.metadata

        # Check that the modified output matches our intervention mock
        assert (
            result.metadata["modified_output"]
            == MOCK_APPLY_GUARDRAIL_INTERVENTION_RESPONSE["outputs"][0]["text"]
        )

        # Check usage data
        assert result.metadata["usage"]["inputTokens"] == 25
        assert result.metadata["usage"]["outputTokens"] == 30
        assert result.metadata["usage"]["totalTokens"] == 55


@pytest.mark.skip_clickhouse_client
@mock_aws
def test_bedrock_invoke_exception_handling(
    client: weave.trace.weave_client.WeaveClient,
) -> None:
    """Test that the postprocessor handles exceptions gracefully without crashing."""
    bedrock_client = boto3.client("bedrock-runtime", region_name="us-east-1")
    patch_client(bedrock_client)

    with patch(
        "botocore.client.BaseClient._make_api_call",
        new=mock_invoke_exception_make_api_call,
    ):
        # Call invoke_model with an invalid model ID that will trigger a ValidationException
        body = json.dumps(
            {
                "anthropic_version": "bedrock-2023-05-31",
                "max_tokens": 30,
                "temperature": 0.7,
                "messages": [{"role": "user", "content": invoke_prompt}],
            }
        )

        # The call should raise a ValidationException
        with pytest.raises(Exception) as exc_info:
            bedrock_client.invoke_model(
                modelId="invalid-model-id",
                body=body,
                contentType="application/json",
                accept="application/json",
            )

        # Verify it's the correct exception
        assert "ValidationException" in str(exc_info.value)
        assert "The provided model identifier is invalid" in str(exc_info.value)

    # Check that a trace was captured even with the exception
    calls = list(client.get_calls())
    assert len(calls) == 1, "Expected exactly one trace call even with exception"
    call = calls[0]

    # Verify the exception was captured in the trace
    assert call.exception is not None
    assert "ValidationException" in str(call.exception)
    assert call.ended_at is not None

    # Verify the output is None (since the call failed)
    assert call.output is None


@pytest.mark.skip_clickhouse_client
@mock_aws
def test_bedrock_agent_invoke_agent(
    client: weave.trace.weave_client.WeaveClient,
) -> None:
    """Test that bedrock-agent-runtime invoke_agent method is properly traced."""
    bedrock_agent_client = boto3.client(
        "bedrock-agent-runtime", region_name="us-east-1"
    )
    patch_client(bedrock_agent_client)

    with patch(
        "botocore.client.BaseClient._make_api_call", new=mock_invoke_agent_make_api_call
    ):
        response = bedrock_agent_client.invoke_agent(
            agentId="test-agent-id",
            agentAliasId="test-alias-id",
            sessionId="test-session-id",
            inputText="Hello, how can you help me?",
        )

        # Basic assertions on the response
        assert response is not None
        assert "completion" in response
        assert "sessionId" in response
        assert response["sessionId"] == "test-session"

    # Check that a trace was captured
    calls = list(client.get_calls())
    assert len(calls) == 1, "Expected exactly one trace call for invoke_agent"
    call = calls[0]

    assert call.exception is None
    assert call.ended_at is not None
    assert "BedrockAgentRuntime.invoke_agent" in call.op_name
    # Verify inputs were captured
    inputs = call.inputs
    assert inputs["agentId"] == "test-agent-id"
    assert inputs["agentAliasId"] == "test-alias-id"
    assert inputs["sessionId"] == "test-session-id"
    assert inputs["inputText"] == "Hello, how can you help me?"

    # Basic usage tracking (detailed token extraction requires complex mocking)
    summary = call.summary
    assert summary is not None, "Summary should not be None"
    assert "usage" in summary


@pytest.mark.skip_clickhouse_client
@mock_aws
def test_bedrock_invoke_stream(client: weave.trace.weave_client.WeaveClient) -> None:
    """
    Requirement: Streaming invoke_model calls are traced with token usage
    Interface: patch_client patches invoke_model_with_response_stream, traces appear in Weave
    Given: A Bedrock runtime client that has been patched with patch_client()
    When: The user calls invoke_model_with_response_stream() and iterates through the response
    Then: A trace is captured with accumulated content and token usage in the summary
    """
    bedrock_client = boto3.client("bedrock-runtime", region_name="us-east-1")
    patch_client(bedrock_client)

    with patch(
        "botocore.client.BaseClient._make_api_call",
        new=mock_invoke_stream_make_api_call,
    ):
        body = json.dumps(
            {
                "anthropic_version": "bedrock-2023-05-31",
                "max_tokens": 30,
                "temperature": 0.7,
                "messages": [{"role": "user", "content": invoke_prompt}],
            }
        )

        response = bedrock_client.invoke_model_with_response_stream(
            modelId=model_id,
            body=body,
            contentType="application/json",
            accept="application/json",
        )

        # Consume the stream to trigger accumulation
        stream = response.get("body")
        assert stream is not None, "Stream body not found in response"

        accumulated_text = ""
        for event in stream:
            if "chunk" in event:
                chunk_data = json.loads(event["chunk"]["bytes"].decode("utf-8"))
                if chunk_data.get("type") == "content_block_delta":
                    delta = chunk_data.get("delta", {})
                    if delta.get("type") == "text_delta":
                        accumulated_text += delta.get("text", "")

        assert "To list all text files" in accumulated_text

    # Verify that a trace was captured
    calls = list(client.get_calls())
    assert len(calls) == 1, "Expected exactly one trace call for streaming invoke"
    call = calls[0]

    assert call.exception is None
    assert call.ended_at is not None
    assert "BedrockRuntime.invoke_stream" in call.op_name

    # Check the accumulated output contains the streamed content
    output = call.output
    assert output is not None
    assert "content" in output
    assert "To list all text files" in output["content"]

    # Verify token usage in summary
    summary = call.summary
    assert summary is not None, "Summary should not be None"
    model_usage = summary["usage"][model_id]
    assert model_usage["requests"] == 1
    # Token counts from streaming: input_tokens=40 from message_start, output_tokens=30 from message_delta
    assert model_usage["prompt_tokens"] == 40
    assert model_usage["completion_tokens"] == 30
    assert model_usage["total_tokens"] == 70


@pytest.mark.skip_clickhouse_client
@mock_aws
def test_bedrock_invoke_stream_exception_handling(
    client: weave.trace.weave_client.WeaveClient,
) -> None:
    """
    Requirement: Exceptions during streaming invoke are captured in traces
    Interface: patch_client patches invoke_model_with_response_stream, exceptions are traced
    Given: A patched Bedrock client where the API call raises a validation exception
    When: The user calls invoke_model_with_response_stream() with invalid parameters
    Then: The exception is raised and captured in the trace
    """
    bedrock_client = boto3.client("bedrock-runtime", region_name="us-east-1")
    patch_client(bedrock_client)

    with patch(
        "botocore.client.BaseClient._make_api_call",
        new=mock_invoke_stream_exception_make_api_call,
    ):
        body = json.dumps(
            {
                "anthropic_version": "bedrock-2023-05-31",
                "max_tokens": 30,
                "temperature": 0.7,
                "messages": [{"role": "user", "content": invoke_prompt}],
            }
        )

        with pytest.raises(Exception) as exc_info:
            bedrock_client.invoke_model_with_response_stream(
                modelId="invalid-model-id",
                body=body,
                contentType="application/json",
                accept="application/json",
            )

        assert "ValidationException" in str(exc_info.value)
        assert "The provided model identifier is invalid" in str(exc_info.value)

    # Check that a trace was captured even with the exception
    calls = list(client.get_calls())
    assert len(calls) == 1, "Expected exactly one trace call even with exception"
    call = calls[0]

    # Verify the exception was captured in the trace
    assert call.exception is not None
    assert "ValidationException" in str(call.exception)
    assert call.ended_at is not None
    assert call.output is None
