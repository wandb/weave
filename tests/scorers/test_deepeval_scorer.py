import pytest
# import asyncio
from unittest.mock import patch

from weave.scorers.deepeval_scorer import (
    DeepEvalContextualPrecisionScorer,
    DeepEvalContextualRecallScorer,
    DeepEvalFaithfulnessScorer,
    DeepEvalAnswerRelevancyScorer,
)

class MockDeepEvalMetric:
    def __init__(self, **kwargs):
        self.score = 1.0
        self.reason = "Mocked reason: This is a successful test."
    async def a_measure(self, test_case):
        pass

class MockLLMTestCase:
    def __init__(self, **kwargs):
        pass

@pytest.mark.asyncio
@patch('weave.scorers.deepeval_scorer.ContextualPrecisionMetric', new=MockDeepEvalMetric)
@patch('weave.scorers.deepeval_scorer.LLMTestCase', new=MockLLMTestCase)
async def test_deepeval_contextual_precision_scorer():
    scorer = DeepEvalContextualPrecisionScorer(model_id="mock-model")
    result = await scorer.score(
        output="Paris is the capital of France.",
        input="What is the capital of France?",
        expected_output="The capital of France is Paris.",
        context=["France's capital is Paris.", "The sky is blue."]
    )
    assert result['score'] == 1.0
    assert "Mocked reason" in result['reason']


@pytest.mark.asyncio
@patch('weave.scorers.deepeval_scorer.ContextualRecallMetric', new=MockDeepEvalMetric)
@patch('weave.scorers.deepeval_scorer.LLMTestCase', new=MockLLMTestCase)
async def test_deepeval_contextual_recall_scorer():
    scorer = DeepEvalContextualRecallScorer(model_id="mock-model")
    result = await scorer.score(
        output="Paris is the capital.",
        input="What is France's capital?",
        expected_output="The capital of France is Paris.",
        context=["France's capital city is Paris."]
    )
    assert result['score'] == 1.0
    assert "Mocked reason" in result['reason']


@pytest.mark.asyncio
@patch('weave.scorers.deepeval_scorer.FaithfulnessMetric', new=MockDeepEvalMetric)
@patch('weave.scorers.deepeval_scorer.LLMTestCase', new=MockLLMTestCase)
async def test_deepeval_faithfulness_scorer():
    scorer = DeepEvalFaithfulnessScorer(model_id="mock-model")
    result = await scorer.score(
        output="Paris is the capital of France.",
        input="What is France's capital?",
        context=["Paris is the capital city of France."]
    )
    assert result['score'] == 1.0
    assert "Mocked reason" in result['reason']


@pytest.mark.asyncio
@patch('weave.scorers.deepeval_scorer.AnswerRelevancyMetric', new=MockDeepEvalMetric)
@patch('weave.scorers.deepeval_scorer.LLMTestCase', new=MockLLMTestCase)
async def test_deepeval_answer_relevancy_scorer():
    scorer = DeepEvalAnswerRelevancyScorer(model_id="mock-model")
    result = await scorer.score(
        output="Paris is the capital of France.",
        input="What is the capital of France?"
    )
    assert result['score'] == 1.0
    assert "Mocked reason" in result['reason']