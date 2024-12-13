import pytest
from unittest.mock import MagicMock

import weave
from weave.scorers.coherence_scorer import CoherenceScorer
from tests.scorers.test_utils import generate_large_text


@pytest.fixture
def coherence_scorer(monkeypatch):
    # Mock model loading
    mock_model = MagicMock()
    mock_tokenizer = MagicMock()
    monkeypatch.setattr("transformers.AutoModelForSequenceClassification.from_pretrained", lambda *args, **kwargs: mock_model)
    monkeypatch.setattr("transformers.AutoTokenizer.from_pretrained", lambda *args, **kwargs: mock_tokenizer)

    # Mock wandb login and project
    monkeypatch.setattr("wandb.login", lambda *args, **kwargs: True)
    mock_project = MagicMock()
    monkeypatch.setattr("wandb.Api", lambda: MagicMock(project=lambda *args: mock_project))

    scorer = CoherenceScorer(
        model_name_or_path="wandb/coherence_scorer",
        device="cpu",
        name="test-coherence",
        description="Test coherence scorer",
        column_map={"output": "text"}
    )

    def mock_pipeline(*args, **kwargs):
        def inner(inputs):
            if "incoherent" in str(inputs.get("text_pair", "")) or "incoherent" in str(inputs.get("text", "")):
                return {"label": "Completely Incoherent", "score": 0.2}
            return {"label": "Perfectly Coherent", "score": 0.95}
        return inner

    monkeypatch.setattr("transformers.pipeline", mock_pipeline)
    return scorer


def test_score_messages_with_coherent_output(coherence_scorer):
    prompt = "This is a test prompt."
    output = "This is a coherent response."
    result = coherence_scorer.score_messages(prompt, output)
    assert result["coherent"]
    assert result["coherence"] == "coherent"
    assert result["coherence_score"] == pytest.approx(0.95)


def test_score_messages_with_incoherent_output(coherence_scorer):
    prompt = "This is a test prompt."
    output = "This is an incoherent response."
    result = coherence_scorer.score_messages(prompt, output)
    assert not result["coherent"]
    assert result["coherence"] == "incoherent"
    assert result["coherence_score"] == pytest.approx(0.2)


@pytest.mark.asyncio
async def test_score_with_chat_history(coherence_scorer):
    prompt = "This is a test prompt."
    output = "This is a coherent response."
    chat_history = [
        {"role": "user", "text": "Hello"},
        {"role": "assistant", "text": "Hi"},
    ]
    result = await coherence_scorer.score(prompt, output, chat_history=chat_history)
    assert result["coherent"]
    assert result["coherence"] == "coherent"
    assert result["coherence_score"] == pytest.approx(0.95)


@pytest.mark.asyncio
async def test_score_with_context(coherence_scorer):
    prompt = "This is a test prompt."
    output = "This is a coherent response."
    context = "This is additional context."
    result = await coherence_scorer.score(prompt, output, context=context)
    assert result["coherent"]
    assert result["coherence"] == "coherent"
    assert result["coherence_score"] == pytest.approx(0.95)


@pytest.mark.asyncio
async def test_coherence_scorer_evaluation(coherence_scorer):
    dataset = [
        {"input": "This is a coherent text."},
        {"input": "This is an incoherent text."},
    ]

    @weave.op
    def model(input: str):
        return input

    evaluation = weave.Evaluation(
        dataset=dataset,
        scorers=[coherence_scorer],
    )
    result = await evaluation.evaluate(model)

    assert "CoherenceScorer" in result
    assert "coherent" in result["CoherenceScorer"]
    assert result["CoherenceScorer"]["coherent"]["true_count"] == 1
    assert result["CoherenceScorer"]["coherent"]["true_fraction"] == pytest.approx(0.5)


@pytest.mark.asyncio
async def test_coherence_scorer_large_input(coherence_scorer):
    large_text = generate_large_text()

    result = await coherence_scorer.score(
        input="What is the story about?",
        output=large_text
    )

    assert "coherent" in result
    assert "coherence" in result
    assert "coherence_score" in result


@pytest.mark.asyncio
async def test_coherence_scorer_error_handling(coherence_scorer):
    with pytest.raises(ValueError):
        await coherence_scorer.score(input="", output="")
