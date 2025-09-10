import pytest

from weave.scorers.coherence_scorer import WeaveCoherenceScorerV1
from weave.scorers.default_models import MODEL_PATHS


@pytest.fixture
def weave_coherence_scorer():
    """Fixture to return a WeaveCoherenceScorer instance."""
    scorer = WeaveCoherenceScorerV1(
        model_name_or_path=MODEL_PATHS["coherence_scorer"],
        device="cpu",
    )
    return scorer


def test_score_messages(weave_coherence_scorer):
    """Test score_messages with a coherent response."""
    query = "This is a test prompt."
    output = "This is a coherent response."
    result = weave_coherence_scorer._score_messages(query, output)
    # Check that the pydantic model has the expected attributes.
    assert result.metadata is not None
    assert result.metadata["coherence_label"] == "Perfectly Coherent"


@pytest.mark.asyncio
async def test_score_with_chat_history(weave_coherence_scorer):
    """Test the score method with chat history."""
    query = "This is a test prompt."
    output = "This is a coherent response."
    # Use the expected key "content" rather than "text"
    chat_history = [
        {"role": "user", "content": "Hello"},
        {"role": "assistant", "content": "Hi"},
    ]
    # Call score using the new argument names.
    result = weave_coherence_scorer.score(
        query=query, output=output, chat_history=chat_history
    )
    assert result.metadata is not None
    assert result.metadata["coherence_label"] == "Perfectly Coherent"


@pytest.mark.asyncio
async def test_incoherent_response(weave_coherence_scorer):
    """Test  with incoherent response."""
    query = "This is a test prompt."
    output = "The grass moon ducks by they"
    # Call score with the context parameter.
    result = weave_coherence_scorer.score(query=query, output=output)
    assert not result.passed


@pytest.mark.asyncio
async def test_score_with_context(weave_coherence_scorer):
    """Test the score method with additional context."""
    query = "This is a test prompt."
    output = "This is a coherent response."
    context = "This is additional context."
    # Call score with the context parameter.
    result = weave_coherence_scorer.score(query=query, output=output, context=context)
    assert result.metadata is not None
    assert result.metadata["coherence_label"] == "Perfectly Coherent"
