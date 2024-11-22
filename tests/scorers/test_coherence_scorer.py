import pytest

import weave
from weave.scorers.coherence_scorer import CoherenceScorer


@pytest.fixture
def coherence_scorer(monkeypatch):
    scorer = CoherenceScorer(
        model_name="wandb/coherence_scorer",
        device="cpu",
    )

    def mock_pipeline(*args, **kwargs):
        def inner(inputs):
            if "incoherent" in inputs["text_pair"] or "incoherent" in inputs["text"]:
                return {
                    "label": "incoherent",
                    "score": 0.2,
                }
            return {
                "label": "coherent",
                "score": 0.95,
            }

        return inner

    monkeypatch.setattr(scorer, "_classifier", mock_pipeline())
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
