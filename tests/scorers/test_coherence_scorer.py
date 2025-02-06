import pytest

from tests.scorers.test_utils import TINY_MODEL_PATHS
from weave.scorers.coherence_scorer import WeaveCoherenceScorer
from weave.scorers.utils import download_model


@pytest.fixture
def weave_coherence_scorer():
    """Fixture to return a WeaveCoherenceScorer instance."""
    tiny_model_path = download_model(TINY_MODEL_PATHS["coherence_scorer"])
    scorer = WeaveCoherenceScorer(
        model_name_or_path=tiny_model_path,
        device="cpu",
    )
    return scorer


def test_score_messages(weave_coherence_scorer):
    """Test score_messages with a coherent response."""
    prompt = "This is a test prompt."
    output = "This is a coherent response."
    result = weave_coherence_scorer.score_messages(prompt, output)
    # Now we check the updated payload structure
    assert "pass" in result
    assert "extras" in result
    assert result["extras"]["coherence_label"] == "A Little Incoherent"


@pytest.mark.asyncio
def test_score_with_chat_history(weave_coherence_scorer):
    """Test the async .score method with chat history."""
    prompt = "This is a test prompt."
    output = "This is a coherent response."
    chat_history = [
        {"role": "user", "text": "Hello"},
        {"role": "assistant", "text": "Hi"},
    ]
    result = weave_coherence_scorer.score(prompt, output, chat_history=chat_history)
    assert "pass" in result
    assert "extras" in result
    assert result["extras"]["coherence_label"] == "A Little Incoherent"


@pytest.mark.asyncio
def test_score_with_context(weave_coherence_scorer):
    """Test the async .score method with additional context."""
    prompt = "This is a test prompt."
    output = "This is a coherent response."
    context = "This is additional context."
    result = weave_coherence_scorer.score(prompt, output, context=context)
    assert "pass" in result
    assert "extras" in result
    assert result["extras"]["coherence_label"] == "A Little Incoherent"
