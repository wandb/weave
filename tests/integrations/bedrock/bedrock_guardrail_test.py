from unittest.mock import MagicMock, patch

import pytest

from weave.scorers.bedrock_guardrails import BedrockGuardrailScorer

# Mock responses for the apply_guardrail API
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
    "action": "ALLOW",
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


@pytest.fixture
def mock_bedrock_client():
    """Create a mock Bedrock client."""
    client = MagicMock()
    # Mock the apply_guardrail method
    client.apply_guardrail = MagicMock()
    return client


@pytest.fixture
def scorer(mock_bedrock_client):
    """Create a BedrockGuardrailScorer instance with a mock client."""
    scorer = BedrockGuardrailScorer(
        guardrail_id="test-guardrail-id",
        guardrail_version="DRAFT",
        source="OUTPUT",
        bedrock_runtime_kwargs={"region_name": "us-east-1"},
    )
    # Replace the real client with our mock
    scorer._bedrock_runtime = mock_bedrock_client
    return scorer


def test_format_content(scorer):
    """Test the format_content method formats content correctly."""
    output = "This is a test output"
    formatted = scorer.format_content(output)

    assert formatted["source"] == "OUTPUT"
    assert len(formatted["content"]) == 1
    assert formatted["content"][0]["text"]["text"] == output


def test_format_content_different_source():
    """Test format_content with a different source parameter."""
    scorer = BedrockGuardrailScorer(
        guardrail_id="test-guardrail-id",
        guardrail_version="DRAFT",
        source="INPUT",  # Using INPUT instead of OUTPUT
        bedrock_runtime_kwargs={"region_name": "us-east-1"},
    )

    output = "Test content"
    formatted = scorer.format_content(output)
    assert formatted["source"] == "INPUT"


def test_client_parameters(mock_bedrock_client):
    """Test that client parameters are passed correctly."""
    # Test with different guardrail_id
    scorer = BedrockGuardrailScorer(
        guardrail_id="custom-guardrail-id",
        guardrail_version="DRAFT",
        source="OUTPUT",
        bedrock_runtime_kwargs={"region_name": "us-east-1"},
    )
    scorer._bedrock_runtime = mock_bedrock_client
    mock_bedrock_client.apply_guardrail.return_value = MOCK_APPLY_GUARDRAIL_RESPONSE

    scorer.score("Test content")
    call_args = mock_bedrock_client.apply_guardrail.call_args[1]
    assert call_args["guardrailIdentifier"] == "custom-guardrail-id"

    # Test with different guardrail_version
    scorer = BedrockGuardrailScorer(
        guardrail_id="test-guardrail-id",
        guardrail_version="2",  # Using a specific version instead of DRAFT
        source="OUTPUT",
        bedrock_runtime_kwargs={"region_name": "us-east-1"},
    )
    scorer._bedrock_runtime = mock_bedrock_client
    mock_bedrock_client.apply_guardrail.return_value = MOCK_APPLY_GUARDRAIL_RESPONSE

    scorer.score("Test content")
    call_args = mock_bedrock_client.apply_guardrail.call_args[1]
    assert call_args["guardrailVersion"] == "2"

    # Test with different source
    scorer = BedrockGuardrailScorer(
        guardrail_id="test-guardrail-id",
        guardrail_version="DRAFT",
        source="INPUT",  # Using INPUT instead of OUTPUT
        bedrock_runtime_kwargs={"region_name": "us-east-1"},
    )
    scorer._bedrock_runtime = mock_bedrock_client
    mock_bedrock_client.apply_guardrail.return_value = MOCK_APPLY_GUARDRAIL_RESPONSE

    scorer.score("Test content")
    call_args = mock_bedrock_client.apply_guardrail.call_args[1]
    assert call_args["source"] == "INPUT"


def test_error_handling(scorer, mock_bedrock_client):
    """Test error handling in the score method."""
    # Mock raises an exception
    mock_bedrock_client.apply_guardrail.side_effect = Exception("Test error")

    result = scorer.score("Test content")

    # Verify the result is properly formatted for error case
    assert result.passed is False
    assert "reason" in result.metadata
    assert "Error applying Bedrock guardrail: Test error" in result.metadata["reason"]
    assert "error" in result.metadata
    assert "Test error" in str(result.metadata["error"])


def test_uninitialized_client():
    """Test handling of uninitialized client."""
    scorer = BedrockGuardrailScorer(
        guardrail_id="test-guardrail-id",
        guardrail_version="DRAFT",
        source="OUTPUT",
        bedrock_runtime_kwargs={"region_name": "us-east-1"},
    )

    # Set the client to None to simulate uninitialized client
    scorer._bedrock_runtime = None

    with pytest.raises(ValueError) as excinfo:
        scorer.score("Test content")

    assert "Bedrock runtime client is not initialized" in str(excinfo.value)


def test_missing_boto3():
    """Test handling of missing boto3 dependency."""
    with patch.dict("sys.modules", {"boto3": None}):
        with pytest.raises(ImportError) as excinfo:
            BedrockGuardrailScorer(
                guardrail_id="test-guardrail-id",
                guardrail_version="DRAFT",
                source="OUTPUT",
                bedrock_runtime_kwargs={"region_name": "us-east-1"},
            )

        assert "boto3 is not installed" in str(excinfo.value)


def test_client_initialization_error():
    """Test handling of client initialization errors."""
    with patch("boto3.client") as mock_boto3_client:
        mock_boto3_client.side_effect = Exception("Failed to initialize client")

        with pytest.raises(Exception) as excinfo:
            BedrockGuardrailScorer(
                guardrail_id="test-guardrail-id",
                guardrail_version="DRAFT",
                source="OUTPUT",
                bedrock_runtime_kwargs={"region_name": "us-east-1"},
            )

        assert "Failed to initialize Bedrock runtime client" in str(excinfo.value)
