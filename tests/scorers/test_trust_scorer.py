import asyncio

import pytest

import weave
from tests.scorers.test_utils import TINY_MODEL_PATHS
from weave.flow.scorer import WeaveScorerResult
from weave.scorers.trust_scorer import WeaveTrustScorerV1


@pytest.fixture
def dummy_scorer():
    "Dummy scorer to test _filter_inputs_for_scorer functionality."

    class DummyScorer(weave.Scorer):
        @weave.op
        def score(self, output: str, query: str):
            return WeaveScorerResult(passed=True, metadata={"dummy": True, "score": 1})

    return DummyScorer()


@pytest.fixture
def trust_scorer():
    scorer = WeaveTrustScorerV1(
        device="cpu",
        context_relevance_model_name_or_path=TINY_MODEL_PATHS["relevance_scorer"],
        hallucination_model_name_or_path=TINY_MODEL_PATHS["hallucination_scorer"],
        toxicity_model_name_or_path=TINY_MODEL_PATHS["toxicity_scorer"],
        fluency_model_name_or_path=TINY_MODEL_PATHS["fluency_scorer"],
        coherence_model_name_or_path=TINY_MODEL_PATHS["coherence_scorer"],
        run_in_parallel=False,
    )
    return scorer


def test_simple_score(trust_scorer):
    result = trust_scorer.score(
        output="dummy output", context="dummy context", query="dummy query"
    )
    assert not result.passed


def test_preprocess_text(trust_scorer):
    input_text = "Hello  ,   world  !"
    # After collapsing spaces -> "Hello , world !" and then punctuation cleanup yields "Hello, world!"
    expected = "Hello, world!"
    processed = trust_scorer._preprocess_text(input_text)
    assert processed == expected


def test_filter_inputs_for_scorer(trust_scorer, dummy_scorer):
    inputs = {
        "output": "test_output",
        "query": "test_query",
        "extra": "should_be_filtered",
    }
    filtered = trust_scorer._filter_inputs_for_scorer(dummy_scorer, inputs)
    assert "output" in filtered
    assert "query" in filtered
    assert "extra" not in filtered


def test_score_all_with_dummy_scorers(trust_scorer):
    # Replace the loaded scorers with dummy ones to simulate controlled outcomes.
    class AlwaysPassScore(weave.Scorer):
        @weave.op
        def score(self, **kwargs):
            return WeaveScorerResult(passed=True, metadata={"score": 0.1})

    class AlwaysFailScore(weave.Scorer):
        @weave.op
        def score(self, **kwargs):
            return WeaveScorerResult(passed=False, metadata={"score": 0.9})

    trust_scorer._loaded_scorers = {
        "AlwaysPass": AlwaysPassScore(),
        "AlwaysFail": AlwaysFailScore(),
    }

    results = trust_scorer._score_all(
        output="dummy output", context="dummy context", query="dummy query"
    )
    assert "AlwaysPass" in results
    assert "AlwaysFail" in results
    assert results["AlwaysPass"].passed
    assert not results["AlwaysFail"].passed


def test_score_with_logic(trust_scorer):
    # Create dummy critical and advisory scorers to verify nuanced trust logic.
    class DummyCriticalScore(weave.Scorer):
        @weave.op
        def score(self, **kwargs):
            return WeaveScorerResult(
                passed=False, metadata={"score": 0.8, "score_2": 0.8}
            )

    class DummyAdvisoryScore(weave.Scorer):
        @weave.op
        def score(self, **kwargs):
            return WeaveScorerResult(
                passed=False, metadata={"score": 0.4, "score_2": 0.4}
            )

    # Override the loaded scorers and classification sets.
    trust_scorer._loaded_scorers = {
        "DummyCritical": DummyCriticalScore(),
        "DummyAdvisory": DummyAdvisoryScore(),
    }
    trust_scorer._critical_scorers = {DummyCriticalScore}
    trust_scorer._advisory_scorers = {DummyAdvisoryScore}

    result = trust_scorer._score_with_logic(
        query="dummy query", context="dummy context", output="dummy output"
    )
    # Since a critical scorer failed, overall trust should be low.
    assert result.metadata["trust_level"] == "low_critical-issues-found"
    assert not result.passed
    assert "DummyCritical" in result.metadata["critical_issues"]
    # Presence of advisory issues should still be reported.
    assert "DummyAdvisory" in result.metadata["advisory_issues"]


# we need to test parallelism and how it plays with weave.Evaluations
def test_trust_scorer_parallelism(trust_scorer):
    trust_scorer.run_in_parallel = True

    ds = [
        {
            "output": "test_output",
            "query": "test_query",
            "context": "context",
        }
    ] * 100

    @weave.op
    def model(output):
        return output

    evaluation = weave.Evaluation(dataset=ds, scorers=[trust_scorer])
    eval_result = asyncio.run(evaluation.evaluate(model))
    assert "passed" in eval_result["WeaveTrustScorerV1"]
    assert "metadata" in eval_result["WeaveTrustScorerV1"]
    assert len(eval_result["WeaveTrustScorerV1"]["metadata"]["raw_outputs"]) == 5

    # Check that none of the subscorers passed
    raw_outputs = eval_result["WeaveTrustScorerV1"]["metadata"]["raw_outputs"]

    # it's kind of boring...
    for _, scorer_results in raw_outputs.items():
        assert scorer_results["passed"]["true_count"] == 0
        assert scorer_results["passed"]["true_fraction"] == 0.0

    # Verify specific mean scores
    assert raw_outputs["WeaveHallucinationScorerV1"]["metadata"]["score"][
        "mean"
    ] == pytest.approx(0.99999, rel=1e-4)
    assert raw_outputs["WeaveCoherenceScorerV1"]["metadata"]["score"][
        "mean"
    ] == pytest.approx(0.20488, rel=1e-4)
    assert raw_outputs["WeaveFluencyScorerV1"]["metadata"]["score"][
        "mean"
    ] == pytest.approx(0.40745, rel=1e-4)
    assert raw_outputs["WeaveContextRelevanceScorerV1"]["metadata"]["score"][
        "mean"
    ] == pytest.approx(0.11111, rel=1e-4)

    # Verify toxicity categories
    toxicity_results = raw_outputs["WeaveToxicityScorerV1"]["metadata"]
    assert toxicity_results["Ability"]["mean"] == 0.0
    assert toxicity_results["Gender/Sex"]["mean"] == 0.0
    assert toxicity_results["Violence"]["mean"] == 2.0
    assert toxicity_results["Race/Origin"]["mean"] == 3.0
    assert toxicity_results["Religion"]["mean"] == 2.0
