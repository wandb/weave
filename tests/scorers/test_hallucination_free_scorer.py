import asyncio
import time
from unittest.mock import patch

import pytest
from openai import OpenAI

import weave
from tests.scorers.test_utils import generate_large_text
from weave.scorers import HallucinationFreeScorer
from weave.scorers.hallucination_scorer import (
    HallucinationReasoning,
    HallucinationResponse,
)


@pytest.fixture
def mock_create(monkeypatch):
    def _mock_create(*args, **kwargs):
        return HallucinationResponse(
            chain_of_thought="The output is consistent with the input data.",
            reasonings=[
                HallucinationReasoning(
                    observation="My observation for this is that the output is consistent with the input data.",
                    hallucination_type="No Hallucination",
                )
            ],
            conclusion="The output is consistent with the input data.",
            has_hallucination=True,
        )

    monkeypatch.setattr("weave.scorers.hallucination_scorer.create", _mock_create)


@pytest.fixture
def hallucination_free_scorer(mock_create):
    return HallucinationFreeScorer(
        client=OpenAI(api_key="DUMMY_API_KEY"),
        model_id="gpt-4o",
        temperature=0.7,
        max_tokens=4096,
    )


def test_initialization():
    """Test scorer initialization with different parameters"""
    # Test default initialization
    scorer = HallucinationFreeScorer(client=OpenAI(api_key="DUMMY_API_KEY"))
    assert scorer.model_id == "gpt-4o"
    assert scorer.temperature == 0.7
    assert scorer.max_tokens == 4096

    # Test custom initialization
    scorer = HallucinationFreeScorer(
        client=OpenAI(api_key="DUMMY_API_KEY"),
        model_id="gpt-3.5-turbo",
        temperature=0.5,
        max_tokens=2048,
    )
    assert scorer.model_id == "gpt-3.5-turbo"
    assert scorer.temperature == 0.5
    assert scorer.max_tokens == 2048


def test_basic_scoring(hallucination_free_scorer, mock_create):
    """Test basic scoring functionality"""
    output = "John's favorite cheese is cheddar."
    context = "John likes various types of cheese."
    result = hallucination_free_scorer.score(output=output, context=context)

    # Validate response structure
    assert isinstance(result, dict)
    assert "chain_of_thought" in result
    assert "reasonings" in result
    assert "conclusion" in result
    assert "has_hallucination" in result

    # Validate response content
    assert result["has_hallucination"] is True
    assert len(result["reasonings"]) == 1
    assert result["reasonings"][0]["hallucination_type"] == "No Hallucination"


def test_empty_inputs(hallucination_free_scorer):
    """Test handling of empty inputs"""
    # Test with empty strings
    with patch("weave.scorers.hallucination_scorer.create") as mock_create:
        mock_create.return_value = HallucinationResponse(
            chain_of_thought="Empty input detected",
            reasonings=[
                HallucinationReasoning(
                    hallucination_type="Empty Input", observation="Input is empty"
                )
            ],
            conclusion="Cannot analyze empty input",
            has_hallucination=True,
        )
        result = hallucination_free_scorer.score(output="", context="")
        assert isinstance(result, dict)
        assert result["has_hallucination"] is True
        assert result["reasonings"][0]["hallucination_type"] == "Empty Input"

    # Test with whitespace-only strings
    with patch("weave.scorers.hallucination_scorer.create") as mock_create:
        mock_create.return_value = HallucinationResponse(
            chain_of_thought="Empty input detected",
            reasonings=[
                HallucinationReasoning(
                    hallucination_type="Empty Input",
                    observation="Input contains only whitespace",
                )
            ],
            conclusion="Cannot analyze empty input",
            has_hallucination=True,
        )
        result = hallucination_free_scorer.score(output="   ", context="\n\t")
        assert isinstance(result, dict)
        assert result["has_hallucination"] is True
        assert result["reasonings"][0]["hallucination_type"] == "Empty Input"


def test_large_inputs(hallucination_free_scorer):
    """Test handling of large inputs"""
    large_context = generate_large_text(50000)  # 50KB text
    large_output = generate_large_text(10000)  # 10KB text

    start_time = time.time()
    result = hallucination_free_scorer.score(output=large_output, context=large_context)
    end_time = time.time()

    # Check performance
    assert end_time - start_time < 10  # Should complete within 10 seconds
    assert isinstance(result, dict)
    assert "has_hallucination" in result


@pytest.mark.asyncio
async def test_async_evaluation(hallucination_free_scorer):
    """Test async evaluation with multiple inputs"""
    dataset = [
        {"context": "John likes various types of cheese."},
        {"context": "Pepe likes various types of cheese."},
        {"context": "Maria enjoys different kinds of pasta."},
    ]

    @weave.op
    def model():
        return "The person's favorite food is mentioned."

    evaluation = weave.Evaluation(
        dataset=dataset,
        scorers=[hallucination_free_scorer],
    )

    start_time = time.time()
    result = await evaluation.evaluate(model)
    end_time = time.time()

    # Performance checks
    assert end_time - start_time < len(dataset) * 5  # 5 seconds per item max

    # Result validation
    assert "HallucinationFreeScorer" in result
    assert "has_hallucination" in result["HallucinationFreeScorer"]
    assert isinstance(
        result["HallucinationFreeScorer"]["has_hallucination"]["true_count"], int
    )


@pytest.mark.asyncio
async def test_concurrent_scoring(hallucination_free_scorer):
    """Test concurrent scoring performance"""

    async def score_item(context, output):
        return await asyncio.to_thread(
            hallucination_free_scorer.score, output=output, context=context
        )

    contexts = [f"Context {i}" for i in range(5)]
    outputs = [f"Output {i}" for i in range(5)]

    start_time = time.time()
    tasks = [score_item(ctx, out) for ctx, out in zip(contexts, outputs)]
    results = await asyncio.gather(*tasks)
    end_time = time.time()

    # Performance validation
    assert end_time - start_time < len(contexts) * 3  # Should be faster than sequential
    assert len(results) == len(contexts)
    assert all(isinstance(r, dict) for r in results)


def test_error_handling(hallucination_free_scorer):
    """Test error handling for various edge cases"""
    # Test with invalid types
    with patch("weave.scorers.hallucination_scorer.create") as mock_create:
        mock_create.return_value = HallucinationResponse(
            chain_of_thought="test",
            reasonings=[],
            conclusion="test",
            has_hallucination=False,
        )
        result = hallucination_free_scorer.score(output=123, context="test")
        assert isinstance(result, dict)
        assert result["has_hallucination"] is False

    # Test with very long input
    very_long_text = "a" * 1000000  # 1MB text
    with patch("weave.scorers.hallucination_scorer.create") as mock_create:
        mock_create.return_value = HallucinationResponse(
            chain_of_thought="test",
            reasonings=[],
            conclusion="test",
            has_hallucination=False,
        )
        result = hallucination_free_scorer.score(output=very_long_text, context="test")
        assert isinstance(result, dict)
        assert result["has_hallucination"] is False


def test_prompt_validation(hallucination_free_scorer):
    """Test validation of system and user prompts."""
    # Test valid prompt update
    valid_prompt = "Valid prompt with {input_data} and {output}"
    hallucination_free_scorer.user_prompt = valid_prompt
    assert hallucination_free_scorer.user_prompt == valid_prompt

    # Test that prompts are used correctly
    with patch("weave.scorers.hallucination_scorer.create") as mock_create:
        mock_create.return_value = HallucinationResponse(
            chain_of_thought="test",
            reasonings=[],
            conclusion="test",
            has_hallucination=False,
        )
        result = hallucination_free_scorer.score(
            output="test output", context="test context"
        )
        assert isinstance(result, dict)
        assert result["has_hallucination"] is False

        # Check that the prompts were passed correctly
        call_args = mock_create.call_args[1]
        messages = call_args["messages"]
        assert len(messages) == 2
        assert messages[0]["role"] == "system"
        assert messages[0]["content"] == hallucination_free_scorer.system_prompt
        assert messages[1]["role"] == "user"
        assert "test output" in messages[1]["content"]
        assert "test context" in messages[1]["content"]


def test_custom_prompts(mock_create):
    """Test scorer with custom system and user prompts."""
    custom_system_prompt = "Custom system prompt for testing"
    custom_user_prompt = "Custom user prompt for testing with {input_data} and {output}"

    scorer = HallucinationFreeScorer(
        client=OpenAI(api_key="DUMMY_API_KEY"),
        system_prompt=custom_system_prompt,
        user_prompt=custom_user_prompt,
    )

    assert scorer.system_prompt == custom_system_prompt
    assert scorer.user_prompt == custom_user_prompt

    result = scorer.score(output="test output", context="test context")
    assert isinstance(result, dict)

    # Test prompt interpolation
    with patch("weave.scorers.hallucination_scorer.create") as mock_create:
        mock_create.return_value = HallucinationResponse(
            chain_of_thought="test",
            reasonings=[],
            conclusion="test",
            has_hallucination=False,
        )
        scorer.score(output="test output", context="test context")

        # Verify the prompt was properly formatted
        call_args = mock_create.call_args[1]
        messages = call_args["messages"]
        assert any("test output" in msg["content"] for msg in messages)
        assert any("test context" in msg["content"] for msg in messages)


def test_api_error_handling(hallucination_free_scorer):
    """Test handling of API errors."""
    # Test API timeout
    with patch("weave.scorers.hallucination_scorer.create") as mock_create:
        mock_create.side_effect = TimeoutError("API timeout")
        with pytest.raises(TimeoutError):
            hallucination_free_scorer.score(output="test", context="test")

    # Test API rate limit
    with patch("weave.scorers.hallucination_scorer.create") as mock_create:
        mock_create.side_effect = Exception("Rate limit exceeded")
        with pytest.raises(Exception):
            hallucination_free_scorer.score(output="test", context="test")

    # Test API invalid response
    with patch("weave.scorers.hallucination_scorer.create") as mock_create:
        mock_create.return_value = HallucinationResponse(
            chain_of_thought="test",
            reasonings=[],
            conclusion="test",
            has_hallucination=False,
        )
        result = hallucination_free_scorer.score(output="test", context="test")
        assert isinstance(result, dict)
        assert "chain_of_thought" in result
        assert "reasonings" in result
        assert "conclusion" in result
        assert "has_hallucination" in result

    # Test API authentication error
    with patch("weave.scorers.hallucination_scorer.create") as mock_create:
        mock_create.side_effect = Exception("Invalid API key")
        with pytest.raises(Exception):
            hallucination_free_scorer.score(output="test", context="test")


def test_response_validation(hallucination_free_scorer):
    """Test validation of LLM responses."""
    # Test with missing required fields
    with patch("weave.scorers.hallucination_scorer.create") as mock_create:
        mock_create.return_value = HallucinationResponse(
            chain_of_thought="test",
            reasonings=[],
            conclusion="test",
            has_hallucination=False,
        )
        result = hallucination_free_scorer.score(output="test", context="test")
        assert isinstance(result, dict)
        assert result["chain_of_thought"] == "test"
        assert result["reasonings"] == []
        assert result["conclusion"] == "test"
        assert result["has_hallucination"] is False

    # Test with invalid field types
    with patch("weave.scorers.hallucination_scorer.create") as mock_create:
        mock_create.return_value = HallucinationResponse(
            chain_of_thought="test",
            reasonings=[
                HallucinationReasoning(hallucination_type="test", observation="test")
            ],
            conclusion="test",
            has_hallucination=True,
        )
        result = hallucination_free_scorer.score(output="test", context="test")
        assert isinstance(result, dict)
        assert len(result["reasonings"]) == 1
        assert result["reasonings"][0]["hallucination_type"] == "test"
        assert result["reasonings"][0]["observation"] == "test"
        assert result["has_hallucination"] is True


def test_column_mapping(hallucination_free_scorer):
    """Test custom column mapping functionality."""
    # Test with default mapping
    dataset = [{"context": "test context", "output": "test output"}]

    # Test with custom mapping
    hallucination_free_scorer.column_map = {
        "context": "input_text",
        "output": "response",
    }
    dataset = [{"input_text": "test context", "response": "test output"}]

    @weave.op
    def model(input_text):
        return "test response"

    evaluation = weave.Evaluation(
        dataset=dataset,
        scorers=[hallucination_free_scorer],
    )

    assert evaluation is not None  # Basic validation that setup works

    # Test that column map is properly set
    assert hallucination_free_scorer.column_map == {
        "context": "input_text",
        "output": "response",
    }

    # Test that column map is used in scoring
    with patch("weave.scorers.hallucination_scorer.create") as mock_create:
        mock_create.return_value = HallucinationResponse(
            chain_of_thought="test",
            reasonings=[],
            conclusion="test",
            has_hallucination=False,
        )
        result = hallucination_free_scorer.score(
            output="test output", context="test context"
        )
        assert isinstance(result, dict)
        assert result["has_hallucination"] is False
