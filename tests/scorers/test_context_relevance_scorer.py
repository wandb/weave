"""Tests for the Context Relevance Scorer."""
import pytest
from unittest.mock import MagicMock
from weave.scorers.context_relevance_scorer import ContextRelevanceScorer
from tests.scorers.test_utils import generate_large_text, generate_context_and_output


@pytest.fixture
def context_relevance_scorer(monkeypatch):
    """Create a context relevance scorer for testing."""
    # Mock wandb login and project
    monkeypatch.setattr("wandb.login", lambda *args, **kwargs: True)
    mock_project = MagicMock()
    monkeypatch.setattr("wandb.Api", lambda: MagicMock(project=lambda *args: mock_project))

    # Mock model loading functions
    monkeypatch.setattr("weave.scorers.llm_utils.download_model", lambda *args, **kwargs: None)
    monkeypatch.setattr("weave.scorers.llm_utils.scorer_model_paths", lambda *args: {"relevance": "mock_path"})
    monkeypatch.setattr("weave.scorers.llm_utils.set_device", lambda *args: "cpu")
    monkeypatch.setattr("weave.scorers.llm_utils.get_model_path", lambda *args: "mock_path")

    scorer = ContextRelevanceScorer(
        model_name_or_path="wandb/relevance_scorer",
        device="cpu",
        name="test-context-relevance",
        description="Test context relevance scorer",
        column_map={"output": "text", "context": "context"}
    )

    def mock_pipeline(*args, **kwargs):
        def inner(text, **kwargs):
            if "irrelevant" in text.lower() or "moon" in text.lower():
                return [{"generated_text": '{"relevance": 0.5, "relevant": false, "flagged": true, "relevance_label": "irrelevant"}'}]
            return [{"generated_text": '{"relevance": 0.9, "relevant": true, "flagged": false, "relevance_label": "relevant"}'}]
        return inner

    monkeypatch.setattr("transformers.pipeline", mock_pipeline)
    monkeypatch.setattr(scorer, "_classifier", mock_pipeline())
    monkeypatch.setattr(scorer, "model_post_init", lambda *args: None)
    return scorer


@pytest.mark.asyncio
async def test_context_relevance_scorer_basic(context_relevance_scorer):
    """Test basic functionality of the context relevance scorer."""
    query = "What is the capital of France?"
    context = "Paris is the capital of France. It is known for the Eiffel Tower."
    output = "The capital of France is Paris."

    result = await context_relevance_scorer.score(
        query=query,
        context=context,
        output=output,
        verbose=True
    )

    assert "flagged" in result
    assert "extras" in result
    assert "score" in result["extras"]
    assert "all_spans" in result["extras"]


@pytest.mark.asyncio
async def test_context_relevance_scorer_large_input(context_relevance_scorer):
    """Test the context relevance scorer with large inputs."""
    query = "What is the story about?"
    context, output = generate_context_and_output(100_000, context_ratio=0.8)

    result = await context_relevance_scorer.score(
        query=query,
        context=context,
        output=output,
        verbose=True
    )

    assert "flagged" in result
    assert "extras" in result
    assert "score" in result["extras"]
    assert "all_spans" in result["extras"]


@pytest.mark.asyncio
async def test_context_relevance_scorer_error_handling(context_relevance_scorer):
    """Test error handling in the context relevance scorer."""
    with pytest.raises(ValueError):
        await context_relevance_scorer.score(
            query="",
            context="",
            output="",
            verbose=True
        )


@pytest.mark.asyncio
async def test_context_relevance_flags_irrelevant(context_relevance_scorer):
    """Test that irrelevant content is properly flagged."""
    query = "What is the capital of France?"
    context = "Paris is the capital of France."
    output = "The moon is made of cheese."

    result = await context_relevance_scorer.score(
        query=query,
        context=context,
        output=output,
        verbose=True
    )

    assert result["flagged"] == True
    assert result["extras"]["score"] < context_relevance_scorer.threshold
    assert not result["extras"]["relevant"]


@pytest.mark.asyncio
async def test_context_relevance_passes_relevant(context_relevance_scorer):
    """Test that relevant content is not flagged."""
    query = "What is the capital of France?"
    context = "Paris is the capital of France."
    output = "The capital of France is Paris."

    result = await context_relevance_scorer.score(
        query=query,
        context=context,
        output=output,
        verbose=True
    )

    assert result["flagged"] == False
    assert result["extras"]["score"] >= context_relevance_scorer.threshold
    assert result["extras"]["relevant"]
