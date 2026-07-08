import io
import json
from collections.abc import Callable
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

# Converse (non-streaming) response reporting prompt-cache token counts.
MOCK_CONVERSE_RESPONSE_CACHE = {
    **MOCK_CONVERSE_RESPONSE,
    "usage": {
        "inputTokens": 100,
        "outputTokens": 20,
        "totalTokens": 120,
        "cacheReadInputTokens": 80,
        "cacheWriteInputTokens": 15,
    },
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

# Converse stream whose metadata reports prompt-cache token counts. Bedrock
# names these cacheReadInputTokens / cacheWriteInputTokens (TokenUsage shape
# in the botocore bedrock-runtime service model — there is no *Count variant).
MOCK_STREAM_EVENTS_CACHE = [
    {"messageStart": {"role": "assistant"}},
    {
        "contentBlockDelta": {
            "delta": {"text": "Cached answer."},
            "contentBlockIndex": 0,
        }
    },
    {"contentBlockStop": {"contentBlockIndex": 0}},
    {"messageStop": {"stopReason": "end_turn"}},
    {
        "metadata": {
            "usage": {
                "inputTokens": 100,
                "outputTokens": 20,
                "totalTokens": 120,
                "cacheReadInputTokens": 80,
                "cacheWriteInputTokens": 15,
            },
            "metrics": {"latencyMs": 500},
        }
    },
]

# Converse stream whose metadata reports a cache read of 0 tokens. A count of 0
# is meaningful (caching was possible but nothing hit) and must be preserved.
MOCK_STREAM_EVENTS_CACHE_ZERO = [
    {"messageStart": {"role": "assistant"}},
    {"contentBlockDelta": {"delta": {"text": "No cache hit."}, "contentBlockIndex": 0}},
    {"contentBlockStop": {"contentBlockIndex": 0}},
    {"messageStop": {"stopReason": "end_turn"}},
    {
        "metadata": {
            "usage": {
                "inputTokens": 100,
                "outputTokens": 20,
                "totalTokens": 120,
                "cacheReadInputTokens": 0,
                "cacheWriteInputTokens": 0,
            },
            "metrics": {"latencyMs": 500},
        }
    },
]

# Converse stream emitting a reasoning block followed by a tool-use block.
# A reasoning-capable, tool-bound Claude model produces these non-text deltas,
# which the accumulator must not choke on.
MOCK_STREAM_EVENTS_TOOL_USE = [
    {"messageStart": {"role": "assistant"}},
    {
        "contentBlockDelta": {
            "delta": {"reasoningContent": {"text": "Let me check"}},
            "contentBlockIndex": 0,
        }
    },
    {
        "contentBlockDelta": {
            "delta": {"reasoningContent": {"text": " the weather."}},
            "contentBlockIndex": 0,
        }
    },
    {
        "contentBlockDelta": {
            "delta": {"reasoningContent": {"signature": "c2lnbmF0dXJl"}},
            "contentBlockIndex": 0,
        }
    },
    {"contentBlockStop": {"contentBlockIndex": 0}},
    {
        "contentBlockStart": {
            "start": {
                "toolUse": {"toolUseId": "tooluse_abc123", "name": "get_weather"}
            },
            "contentBlockIndex": 1,
        }
    },
    {
        "contentBlockDelta": {
            "delta": {"toolUse": {"input": '{"city":'}},
            "contentBlockIndex": 1,
        }
    },
    {
        "contentBlockDelta": {
            "delta": {"toolUse": {"input": ' "Paris"}'}},
            "contentBlockIndex": 1,
        }
    },
    {"contentBlockStop": {"contentBlockIndex": 1}},
    {"messageStop": {"stopReason": "tool_use"}},
    {
        "metadata": {
            "usage": {"inputTokens": 60, "outputTokens": 25, "totalTokens": 85},
            "metrics": {"latencyMs": 500},
        }
    },
]

# A turn with a leading text block followed by two tool-use blocks: exercises
# text/tool interleaving and arg routing across multiple contentBlockStart events.
MOCK_STREAM_EVENTS_TEXT_AND_TOOLS = [
    {"messageStart": {"role": "assistant"}},
    {"contentBlockDelta": {"delta": {"text": "Checking"}, "contentBlockIndex": 0}},
    {"contentBlockDelta": {"delta": {"text": " both."}, "contentBlockIndex": 0}},
    {"contentBlockStop": {"contentBlockIndex": 0}},
    {
        "contentBlockStart": {
            "start": {"toolUse": {"toolUseId": "tool_1", "name": "get_weather"}},
            "contentBlockIndex": 1,
        }
    },
    {
        "contentBlockDelta": {
            "delta": {"toolUse": {"input": '{"city": "Paris"}'}},
            "contentBlockIndex": 1,
        }
    },
    {"contentBlockStop": {"contentBlockIndex": 1}},
    {
        "contentBlockStart": {
            "start": {"toolUse": {"toolUseId": "tool_2", "name": "get_time"}},
            "contentBlockIndex": 2,
        }
    },
    {
        "contentBlockDelta": {
            "delta": {"toolUse": {"input": '{"tz":'}},
            "contentBlockIndex": 2,
        }
    },
    {
        "contentBlockDelta": {
            "delta": {"toolUse": {"input": ' "CET"}'}},
            "contentBlockIndex": 2,
        }
    },
    {"contentBlockStop": {"contentBlockIndex": 2}},
    {"messageStop": {"stopReason": "tool_use"}},
    {
        "metadata": {
            "usage": {"inputTokens": 70, "outputTokens": 40, "totalTokens": 110},
            "metrics": {"latencyMs": 700},
        }
    },
]

MOCK_INVOKE_BODY = json.dumps(
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


def converse_stream_make_api_call(events: list[dict]) -> Callable:
    """Build a _make_api_call that streams the given events for ConverseStream."""

    def mock(self, operation_name: str, api_params: dict) -> dict:
        if operation_name == "ConverseStream":

            class MockStream:
                def __iter__(self):
                    yield from events

            return {"stream": MockStream()}
        return orig(self, operation_name, api_params)

    return mock


def converse_make_api_call(response: dict) -> Callable:
    """Build a _make_api_call that returns the given response for Converse."""

    def mock(self, operation_name: str, api_params: dict) -> dict:
        if operation_name == "Converse":
            return response
        return orig(self, operation_name, api_params)

    return mock


def mock_invoke_make_api_call(self, operation_name: str, api_params: dict) -> dict:
    if operation_name == "InvokeModel":
        # Return a fresh body stream on each call so the response can be consumed
        # independently across parametrized test runs.
        return {
            "body": io.BytesIO(MOCK_INVOKE_BODY),
            "ContentType": "application/json",
        }
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

    # Integration-tracking metadata is stamped on every patched call.
    integration = call.attributes["integration"]
    assert integration["name"] == "bedrock"
    assert integration["version"]  # weave SDK version
    assert integration["meta"]["package_name"] == "boto3"

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


@mock_aws
def test_bedrock_converse_stream_tool_use(
    client: weave.trace.weave_client.WeaveClient,
) -> None:
    """Tool-use and reasoning deltas must not raise KeyError mid-stream (issue #7215)."""
    bedrock_client = boto3.client("bedrock-runtime", region_name="us-east-1")
    patch_client(bedrock_client)

    with patch(
        "botocore.client.BaseClient._make_api_call",
        new=converse_stream_make_api_call(MOCK_STREAM_EVENTS_TOOL_USE),
    ):
        response = bedrock_client.converse_stream(
            modelId=model_id,
            system=[{"text": system_message}],
            messages=messages,
            inferenceConfig={"maxTokens": 100},
        )
        stream = response.get("stream")
        assert stream is not None, "Stream not found in response"

        # The user must receive every event unchanged: non-text deltas previously
        # crashed the wrapper and terminated this loop.
        consumed = list(stream)
        assert consumed == MOCK_STREAM_EVENTS_TOOL_USE

    calls = client.get_calls()
    assert len(calls) == 1, "Expected exactly one trace call for the stream test"
    call = calls[0]
    assert call.exception is None
    assert call.ended_at is not None

    output = call.output
    assert output["role"] == "assistant"
    assert output["content"] == ""
    assert output["reasoning"] == "Let me check the weather."
    assert output["tool_calls"] == [
        {
            "toolUseId": "tooluse_abc123",
            "name": "get_weather",
            "input": '{"city": "Paris"}',
        }
    ]
    assert output["stop_reason"] == "tool_use"

    summary = call.summary
    assert summary is not None, "Summary should not be None"
    model_usage = summary["usage"][model_id]
    assert model_usage["requests"] == 1
    assert output["usage"]["inputTokens"] == model_usage["prompt_tokens"] == 60
    assert output["usage"]["outputTokens"] == model_usage["completion_tokens"] == 25
    assert output["usage"]["totalTokens"] == model_usage["total_tokens"] == 85


@mock_aws
def test_bedrock_converse_stream_text_and_tools(
    client: weave.trace.weave_client.WeaveClient,
) -> None:
    """Leading text plus two tool calls: args route to the right tool block."""
    bedrock_client = boto3.client("bedrock-runtime", region_name="us-east-1")
    patch_client(bedrock_client)

    with patch(
        "botocore.client.BaseClient._make_api_call",
        new=converse_stream_make_api_call(MOCK_STREAM_EVENTS_TEXT_AND_TOOLS),
    ):
        response = bedrock_client.converse_stream(
            modelId=model_id,
            system=[{"text": system_message}],
            messages=messages,
            inferenceConfig={"maxTokens": 100},
        )
        stream = response.get("stream")
        assert stream is not None, "Stream not found in response"
        consumed = list(stream)
        assert consumed == MOCK_STREAM_EVENTS_TEXT_AND_TOOLS

    calls = client.get_calls()
    assert len(calls) == 1, "Expected exactly one trace call for the stream test"
    call = calls[0]
    assert call.exception is None
    assert call.ended_at is not None

    output = call.output
    assert output["content"] == "Checking both."
    assert output["reasoning"] == ""
    assert output["tool_calls"] == [
        {"toolUseId": "tool_1", "name": "get_weather", "input": '{"city": "Paris"}'},
        {"toolUseId": "tool_2", "name": "get_time", "input": '{"tz": "CET"}'},
    ]
    assert output["stop_reason"] == "tool_use"

    summary = call.summary
    assert summary is not None, "Summary should not be None"
    model_usage = summary["usage"][model_id]
    assert model_usage["requests"] == 1
    assert output["usage"]["inputTokens"] == model_usage["prompt_tokens"] == 70
    assert output["usage"]["outputTokens"] == model_usage["completion_tokens"] == 40
    assert output["usage"]["totalTokens"] == model_usage["total_tokens"] == 110


@mock_aws
def test_bedrock_converse_cache_tokens(
    client: weave.trace.weave_client.WeaveClient,
) -> None:
    """Non-streaming converse records prompt-cache token counts."""
    bedrock_client = boto3.client("bedrock-runtime", region_name="us-east-1")
    patch_client(bedrock_client)

    with patch(
        "botocore.client.BaseClient._make_api_call",
        new=converse_make_api_call(MOCK_CONVERSE_RESPONSE_CACHE),
    ):
        bedrock_client.converse(
            modelId=model_id,
            system=[{"text": system_message}],
            messages=messages,
            inferenceConfig={"maxTokens": 30},
        )

    calls = client.get_calls()
    assert len(calls) == 1
    model_usage = calls[0].summary["usage"][model_id]
    # prompt_tokens is gross: inputTokens (100) excludes cached tokens, so the
    # cache read (80) and cache write (15) counts are added in.
    assert model_usage["prompt_tokens"] == 195
    assert model_usage["completion_tokens"] == 20
    assert model_usage["total_tokens"] == 120
    assert model_usage["cache_read_input_tokens"] == 80
    assert model_usage["cache_creation_input_tokens"] == 15


@mock_aws
def test_bedrock_converse_stream_cache_tokens(
    client: weave.trace.weave_client.WeaveClient,
) -> None:
    """Streaming converse records prompt-cache token counts from the metadata event."""
    bedrock_client = boto3.client("bedrock-runtime", region_name="us-east-1")
    patch_client(bedrock_client)

    with patch(
        "botocore.client.BaseClient._make_api_call",
        new=converse_stream_make_api_call(MOCK_STREAM_EVENTS_CACHE),
    ):
        response = bedrock_client.converse_stream(
            modelId=model_id,
            system=[{"text": system_message}],
            messages=messages,
            inferenceConfig={"maxTokens": 30},
        )
        consumed = list(response.get("stream"))
        assert consumed == MOCK_STREAM_EVENTS_CACHE

    calls = client.get_calls()
    assert len(calls) == 1
    model_usage = calls[0].summary["usage"][model_id]
    # Same gross prompt_tokens math as the non-streaming cache test above.
    assert model_usage["prompt_tokens"] == 195
    assert model_usage["completion_tokens"] == 20
    assert model_usage["total_tokens"] == 120
    assert model_usage["cache_read_input_tokens"] == 80
    assert model_usage["cache_creation_input_tokens"] == 15


@mock_aws
def test_bedrock_converse_stream_cache_tokens_zero(
    client: weave.trace.weave_client.WeaveClient,
) -> None:
    """A cache read of 0 is a meaningful count and must be recorded, not dropped."""
    bedrock_client = boto3.client("bedrock-runtime", region_name="us-east-1")
    patch_client(bedrock_client)

    with patch(
        "botocore.client.BaseClient._make_api_call",
        new=converse_stream_make_api_call(MOCK_STREAM_EVENTS_CACHE_ZERO),
    ):
        response = bedrock_client.converse_stream(
            modelId=model_id,
            system=[{"text": system_message}],
            messages=messages,
            inferenceConfig={"maxTokens": 30},
        )
        list(response.get("stream"))

    calls = client.get_calls()
    assert len(calls) == 1
    model_usage = calls[0].summary["usage"][model_id]
    assert model_usage["cache_read_input_tokens"] == 0
    assert model_usage["cache_creation_input_tokens"] == 0
    # Zero cache counts add nothing: prompt_tokens stays at inputTokens.
    assert model_usage["prompt_tokens"] == 100


@mock_aws
@pytest.mark.parametrize("model_identifier", [model_id, inference_profile_id])
def test_bedrock_invoke(
    client: weave.trace.weave_client.WeaveClient, model_identifier: str
) -> None:
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
            modelId=model_identifier,
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
        with pytest.raises(Exception, match="ValidationException") as exc_info:
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
