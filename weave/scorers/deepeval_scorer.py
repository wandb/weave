from typing import Any
import weave
from weave.scorers.default_models import OPENAI_DEFAULT_MODEL
from weave.scorers.scorer_types import LLMScorer

try:
    from deepeval.metrics import (
        ContextualPrecisionMetric,
        ContextualRecallMetric,
        FaithfulnessMetric,
        AnswerRelevancyMetric,
    )
    from deepeval.test_case import LLMTestCase
except ImportError:
    raise


class DeepEvalContextualPrecisionScorer(LLMScorer):
    model_id: str = OPENAI_DEFAULT_MODEL
    threshold: float = 0.5
    include_reason: bool = True
    strict_mode: bool = False

    @weave.op()
    async def score(self, *, output: Any, **kwargs: Any) -> dict:
        input_str = kwargs.get("input")
        expected_output = kwargs.get("expected_output")
        context = kwargs.get("context")

        if not all([input_str, expected_output, context]):
            raise ValueError("ContextualPrecisionScorer requires 'input', 'expected_output', and 'context' in kwargs.")

        metric = ContextualPrecisionMetric(
            threshold=self.threshold, 
            model=self.model_id, 
            include_reason=self.include_reason,
            strict_mode=self.strict_mode, 
            async_mode=True,
        )
        test_case = LLMTestCase(
            input=input_str, 
            actual_output=output, 
            expected_output=expected_output,
            retrieval_context=context
        )
        await metric.a_measure(test_case)
        return {"score": metric.score, "reason": metric.reason}


class DeepEvalContextualRecallScorer(LLMScorer):
    model_id: str = OPENAI_DEFAULT_MODEL
    threshold: float = 0.5
    include_reason: bool = True
    strict_mode: bool = False

    @weave.op()
    async def score(self, *, output: str, **kwargs: Any) -> dict:
        input_str = kwargs.get("input")
        expected_output = kwargs.get("expected_output")
        context = kwargs.get("context")

        assert isinstance(input_str, str)
        assert isinstance(expected_output, str)
        assert isinstance(context, list)

        if not all([input_str, expected_output, context]):
            raise ValueError("ContextualRecallScorer requires 'input', 'expected_output', and 'context' in kwargs.")

        metric = ContextualRecallMetric(
            threshold=self.threshold, model=self.model_id, include_reason=self.include_reason,
            strict_mode=self.strict_mode, async_mode=True,
        )
        test_case = LLMTestCase(
            input=input_str, actual_output=output, expected_output=expected_output,
            retrieval_context=context
        )
        await metric.a_measure(test_case)
        return {"score": metric.score, "reason": metric.reason}


class DeepEvalFaithfulnessScorer(LLMScorer):
    model_id: str = OPENAI_DEFAULT_MODEL
    threshold: float = 0.5
    include_reason: bool = True
    strict_mode: bool = False

    @weave.op()
    async def score(self, *, output: str, **kwargs: Any) -> dict:
        input_str = kwargs.get("input")
        context = kwargs.get("context")

        assert isinstance(input_str, str)
        assert isinstance(context, list)


        if not all([input_str, context]):
            raise ValueError("FaithfulnessScorer requires 'input' and 'context' in kwargs.")

        metric = FaithfulnessMetric(
            threshold=self.threshold, 
            model=self.model_id, 
            include_reason=self.include_reason,
            strict_mode=self.strict_mode, 
            async_mode=True,
        )
        test_case = LLMTestCase(
            input=input_str, actual_output=output, retrieval_context=context
        )
        await metric.a_measure(test_case)
        return {"score": metric.score, "reason": metric.reason}


class DeepEvalAnswerRelevancyScorer(LLMScorer):
    model_id: str = OPENAI_DEFAULT_MODEL
    threshold: float = 0.5
    include_reason: bool = True
    strict_mode: bool = False

    @weave.op()
    async def score(self, *, output: str, **kwargs: Any) -> dict:
        input_str = kwargs.get("input")

        assert isinstance(input_str, str)

        if not input_str:
            raise ValueError("AnswerRelevancyScorer requires 'input' in kwargs.")

        metric = AnswerRelevancyMetric(
            threshold=self.threshold, 
            model=self.model_id, 
            include_reason=self.include_reason,
            strict_mode=self.strict_mode, 
            async_mode=True,
        )
        test_case = LLMTestCase(input=input_str, actual_output=output)
        await metric.a_measure(test_case)
        return {"score": metric.score, "reason": metric.reason}