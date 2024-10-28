import pytest
from openai import OpenAI

import weave
from weave.scorers import (
    SummarizationScorer,
)
from weave.scorers.summarization_scorer import (
    EntityExtractionResponse,
    SummarizationEvaluationResponse,
)


@pytest.fixture
def mock_create(monkeypatch):
    def _mock_create(*args, **kwargs):
        response_model = kwargs.get("response_model")
        if response_model == EntityExtractionResponse:
            return EntityExtractionResponse(entities=["entity1", "entity2"])
        elif response_model == SummarizationEvaluationResponse:
            return SummarizationEvaluationResponse(
                think_step_by_step="This is some reasoning.",
                summarization_evaluation="excellent",
            )

    # Patch the 'create' function wherever it is called
    monkeypatch.setattr("weave.scorers.summarization_scorer.create", _mock_create)


@pytest.fixture
def summarization_scorer(mock_create):
    return SummarizationScorer(
        client=OpenAI(api_key="DUMMY_API_KEY"),
        model_id="gpt-4o",
        temperature=0.7,
        max_tokens=1024,
    )


def test_summarization_scorer_evaluate_summary(summarization_scorer, mock_create):
    input_text = "This is the original text."
    summary_text = "This is the summary."
    result = summarization_scorer.evaluate_summary(
        input=input_text, summary=summary_text
    )
    assert isinstance(result, SummarizationEvaluationResponse)
    assert result.summarization_evaluation == "excellent"
    assert result.think_step_by_step == "This is some reasoning."


@pytest.mark.asyncio
async def test_summarization_scorer_score(summarization_scorer):
    input_text = "This is the original text."
    output_text = "This is the summary."
    result = await summarization_scorer.score(input=input_text, output=output_text)
    assert isinstance(result, dict)
    assert "summarization_eval_score" in result
    assert result["summarization_eval_score"] == 1.0  # "excellent" maps to 1.0
    assert "llm_eval_reasoning" in result
    assert result["llm_eval_reasoning"] == "This is some reasoning."
    assert "is_entity_dense" in result
    assert isinstance(result["is_entity_dense"], bool)
    assert "entity_density" in result
    assert isinstance(result["entity_density"], float)


def test_summarization_scorer_initialization(summarization_scorer):
    assert isinstance(summarization_scorer, SummarizationScorer)
    assert summarization_scorer.model_id == "gpt-4o"
    assert summarization_scorer.temperature == 0.7
    assert summarization_scorer.max_tokens == 1024


def test_summarization_scorer_extract_entities(summarization_scorer):
    text = "This is a sample text with entities."
    entities = summarization_scorer.extract_entities(text)
    assert isinstance(entities, list)
    assert len(entities) == 2
    assert "entity1" in entities
    assert "entity2" in entities


@pytest.mark.asyncio
async def test_evaluate_summary_scorer(summarization_scorer):
    dataset = [
        {
            "input": "This is the original text.",
        },
        {
            "input": "This is another original text.",
        },
    ]
    evaluation = weave.Evaluation(dataset=dataset, scorers=[summarization_scorer])

    @weave.op
    def model(input: str):
        return "This is the summary."

    result = await evaluation.evaluate(model)
    assert isinstance(result, dict)
    assert "SummarizationScorer" in result
    assert "entity_density" in result["SummarizationScorer"]
    assert "is_entity_dense" in result["SummarizationScorer"]
    assert "summarization_eval_score" in result["SummarizationScorer"]
    assert "model_latency" in result

    assert result["SummarizationScorer"]["entity_density"]["mean"] == pytest.approx(0.5)
    assert result["SummarizationScorer"]["is_entity_dense"]["true_count"] == 2
    assert result["SummarizationScorer"]["is_entity_dense"]["true_fraction"] == 1.0
    assert result["SummarizationScorer"]["summarization_eval_score"]["mean"] == 1.0
