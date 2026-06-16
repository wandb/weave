import pytest
from pydantic import BaseModel

import weave
from weave.scorers import (
    SummarizationScorer,
)
from weave.scorers.summarization_scorer import (
    EntityExtractionResponse,
    SummarizationEvaluationResponse,
)


@pytest.fixture
def summarization_scorer(monkeypatch):
    async def _mock_acompletion(*args, **kwargs):
        response_format = kwargs.get("response_format")
        if response_format == EntityExtractionResponse:
            content = '{"entities": ["entity1", "entity2"]}'
        elif response_format == SummarizationEvaluationResponse:
            content = (
                '{"think_step_by_step": "This is some reasoning.", '
                '"summarization_evaluation": "excellent"}'
            )

        class Message(BaseModel):
            content: str

        class Choice(BaseModel):
            message: Message

        class Response(BaseModel):
            choices: list[Choice]

        return Response(choices=[Choice(message=Message(content=content))])

    monkeypatch.setattr(
        "weave.scorers.summarization_scorer.SummarizationScorer._acompletion",
        _mock_acompletion,
    )

    return SummarizationScorer(
        model_id="gpt-4o",
        temperature=0.7,
        max_tokens=1024,
    )


@pytest.mark.asyncio
async def test_summarization_scorer_init_and_methods(summarization_scorer):
    assert isinstance(summarization_scorer, SummarizationScorer)
    assert summarization_scorer.model_id == "gpt-4o"
    assert summarization_scorer.temperature == 0.7
    assert summarization_scorer.max_tokens == 1024

    eval_result = await summarization_scorer._evaluate_summary(
        input="This is the original text.", summary="This is the summary."
    )
    assert isinstance(eval_result, SummarizationEvaluationResponse)
    assert eval_result.summarization_evaluation == "excellent"
    assert eval_result.think_step_by_step == "This is some reasoning."

    entities = await summarization_scorer._extract_entities(
        "This is a sample text with entities."
    )
    assert isinstance(entities, list)
    assert len(entities) == 2
    assert "entity1" in entities
    assert "entity2" in entities

    score = await summarization_scorer.score(
        input="This is the original text.", output="This is the summary."
    )
    assert isinstance(score, dict)
    assert "summarization_eval_score" in score
    assert score["summarization_eval_score"] == 1.0  # "excellent" maps to 1.0
    assert "llm_eval_reasoning" in score
    assert score["llm_eval_reasoning"] == "This is some reasoning."
    assert "is_entity_dense" in score
    assert isinstance(score["is_entity_dense"], bool)
    assert "entity_density" in score
    assert isinstance(score["entity_density"], float)


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
