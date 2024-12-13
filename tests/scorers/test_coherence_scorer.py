import pytest
from unittest.mock import MagicMock

import weave
from weave.scorers.coherence_scorer import CoherenceScorer
from tests.scorers.test_utils import generate_large_text


@pytest.fixture
def coherence_scorer(monkeypatch):
    # Mock wandb login and project
    monkeypatch.setattr("wandb.login", lambda *args, **kwargs: True)
    mock_project = MagicMock()
    monkeypatch.setattr("wandb.Api", lambda: MagicMock(project=lambda *args: mock_project))

    # Mock model loading functions
    monkeypatch.setattr("weave.scorers.llm_utils.download_model", lambda *args, **kwargs: None)
    monkeypatch.setattr("weave.scorers.llm_utils.scorer_model_paths", lambda *args: {"coherence": "mock_path"})
    monkeypatch.setattr("weave.scorers.llm_utils.set_device", lambda *args: "cpu")
    monkeypatch.setattr("weave.scorers.llm_utils.get_model_path", lambda *args: "mock_path")

    scorer = CoherenceScorer(
        model_name_or_path="wandb/coherence_scorer",
        device="cpu",
        name="test-coherence",
        description="Test coherence scorer",
        column_map={"output": "text"}
    )

    # Mock model and tokenizer
    monkeypatch.setattr(scorer, "_model", MagicMock())
    monkeypatch.setattr(scorer, "_tokenizer", MagicMock())
    monkeypatch.setattr(scorer, "model_post_init", lambda *args: None)
    monkeypatch.setattr(scorer, "__private_attributes__", {})
    monkeypatch.setattr(scorer, "__pydantic_private__", {})
    monkeypatch.setattr(scorer, "__pydantic_fields__", {"_model": None, "_tokenizer": None})
    monkeypatch.setattr(scorer, "__pydantic_extra__", {})

    def mock_pipeline(*args, **kwargs):
        def inner(text, **kwargs):
            if "incoherent" in text.lower() or "random" in text.lower() or "hamburger pencil dance" in text.lower():
                return [{"generated_text": '{"coherence": 0.2, "coherent": false, "flagged": true, "coherence_label": "incoherent"}'}]
            return [{"generated_text": '{"coherence": 0.9, "coherent": true, "flagged": false, "coherence_label": "coherent"}'}]
        return inner

    monkeypatch.setattr("transformers.pipeline", mock_pipeline)
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


@pytest.mark.asyncio
async def test_coherence_scorer_flags_incoherent(coherence_scorer):
    result = await coherence_scorer.score(
        input="What is the story about?",
        output="The cat is blue sky hamburger pencil dance."
    )
    assert result["flagged"] == True
    assert "incoherent" in result["extras"]["coherence_label"].lower()
    assert result["extras"]["coherence_score"] < 0.5


@pytest.mark.asyncio
async def test_coherence_scorer_passes_coherent(coherence_scorer):
    result = await coherence_scorer.score(
        input="What is the story about?",
        output="The cat is sleeping peacefully on the windowsill in the afternoon sun."
    )
    assert result["flagged"] == False
    assert "coherent" in result["extras"]["coherence_label"].lower()
    assert result["extras"]["coherence_score"] >= 0.5
