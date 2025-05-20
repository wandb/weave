"""
W&B Trust Score implementation.

This scorer combines multiple scorers to provide a comprehensive trust evaluation.
"""

import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from inspect import signature
from typing import Any, Optional, Union

from pydantic import Field, PrivateAttr, validate_call

import weave
from weave.flow.scorer import WeaveScorerResult
from weave.scorers import (
    WeaveCoherenceScorerV1,
    WeaveContextRelevanceScorerV1,
    WeaveFluencyScorerV1,
    WeaveHallucinationScorerV1,
    WeaveToxicityScorerV1,
)
from weave.scorers.context_relevance_scorer import CONTEXT_RELEVANCE_SCORER_THRESHOLD
from weave.scorers.fluency_scorer import FLUENCY_SCORER_THRESHOLD
from weave.scorers.hallucination_scorer import HALLUCINATION_SCORER_THRESHOLD
from weave.scorers.moderation_scorer import (
    TOXICITY_CATEGORY_THRESHOLD,
    TOXICITY_TOTAL_THRESHOLD,
)


class WeaveTrustScorerError(Exception):
    """Error raised by the WeaveTrustScorerV1."""

    def __init__(self, message: str, errors: Optional[Exception] = None):
        super().__init__(message)
        self.errors = errors


class WeaveTrustScorerV1(weave.Scorer):
    """A comprehensive trust evaluation scorer that combines multiple specialized scorers.

    For best performance run this Scorer on a GPU. The model weights for 5 small language models
    will be downloaded automatically from W&B Artifacts when this Scorer is initialized.

    The TrustScorer evaluates the trustworthiness of model outputs by combining multiple
    specialized scorers into two categories.

    Note: This scorer is suited for RAG pipelines. It requires query, context and output keys to score correctly.

    1. Critical Scorers (automatic failure if pass is False):
        - WeaveToxicityScorerV1: Detects harmful, offensive, or inappropriate content
        - WeaveHallucinationScorerV1: Identifies fabricated or unsupported information
        - WeaveContextRelevanceScorerV1: Ensures output relevance to provided context

    2. Advisory Scorers (warnings that may affect trust):
        - WeaveFluencyScorerV1: Evaluates language quality and coherence
        - WeaveCoherenceScorerV1: Checks for logical consistency and flow

    Trust Levels:
        - "high": No issues detected
        - "medium": Only advisory issues detected
        - "low": Critical issues detected or empty input

    Args:
        device (str): Device for model inference ("cpu", "cuda", "mps", "auto"). Defaults to "cpu".
        context_relevance_model_name_or_path (str, optional): Local path or W&B Artifact path for the context relevance model.
        hallucination_model_name_or_path (str, optional): Local path or W&B Artifact path for the hallucination model.
        toxicity_model_name_or_path (str, optional): Local path or W&B Artifact path for the toxicity model.
        fluency_model_name_or_path (str, optional): Local path or W&B Artifact path for the fluency model.
        coherence_model_name_or_path (str, optional): Local path or W&B Artifact path for the coherence model.
        run_in_parallel (bool): Whether to run scorers in parallel or sequentially, useful for debugging. Defaults to True.

    Note: The `output` parameter of this Scorer's `score` method expects the output of a LLM or AI system.

    Example:
        ```python
        scorer = TrustScorer(run_in_parallel=True)

        # Basic scoring
        result = scorer.score(
            output="The sky is blue.",
            context="Facts about the sky.",
            query="What color is the sky?"
        )

        # Example output:
        WeaveScorerResult(
            passed=True,
            metadata={
                "trust_level": "high_no-issues-found",
                "critical_issues": [],
                "advisory_issues": [],
                "raw_outputs": {
                    "WeaveToxicityScorerV1": {"passed": True, "metadata": {"Race/Origin": 0, "Gender/Sex": 0, "Religion": 0, "Ability": 0, "Violence": 0}},
                    "WeaveHallucinationScorerV1": {"passed": True, "metadata": {"score": 0.1}},
                    "WeaveContextRelevanceScorerV1": {"passed": True, "metadata": {"score": 0.85}},
                    "WeaveFluencyScorerV1": {"passed": True, "metadata": {"score": 0.95}},
                    "WeaveCoherenceScorerV1": {"passed": True, "metadata": {"coherence_label": "Perfectly Coherent", "coherence_id": 4, "score": 0.9}}
                },
                "scores": {
                    "WeaveToxicityScorerV1": {"Race/Origin": 0, "Gender/Sex": 0, "Religion": 0, "Ability": 0, "Violence": 0},
                    "WeaveHallucinationScorerV1": 0.1,
                    "WeaveContextRelevanceScorerV1": 0.85,
                    "WeaveFluencyScorerV1": 0.95,
                    "WeaveCoherenceScorerV1": 0.9
                }
            }
        )
        ```

    """

    # Model configuration
    device: str = Field(
        default="cpu",
        description="Device for model inference ('cpu', 'cuda', 'mps', 'auto')",
        from_default=True,
    )
    context_relevance_model_name_or_path: str = Field(
        default="",
        description="Path or name of the context relevance model",
        validate_default=True,
    )
    hallucination_model_name_or_path: str = Field(
        default="",
        description="Path or name of the hallucination model",
        validate_default=True,
    )
    toxicity_model_name_or_path: str = Field(
        default="",
        description="Path or name of the toxicity model",
        validate_default=True,
    )
    fluency_model_name_or_path: str = Field(
        default="",
        description="Path or name of the fluency model",
        validate_default=True,
    )
    coherence_model_name_or_path: str = Field(
        default="",
        description="Path or name of the coherence model",
        validate_default=True,
    )
    run_in_parallel: bool = Field(
        default=True,
        description="Whether to run scorers in parallel or sequentially, useful for debugging.",
    )

    # Define scorer categories
    _critical_scorers: set[weave.Scorer] = PrivateAttr(
        default_factory=lambda: {
            WeaveToxicityScorerV1,
            WeaveHallucinationScorerV1,
            WeaveContextRelevanceScorerV1,
        }
    )
    _advisory_scorers: set[weave.Scorer] = PrivateAttr(
        default_factory=lambda: {
            WeaveFluencyScorerV1,
            WeaveCoherenceScorerV1,
        }
    )

    # Private attributes
    _loaded_scorers: dict[str, weave.Scorer] = PrivateAttr(default_factory=dict)
    _emoji_pattern: re.Pattern = PrivateAttr(
        default=re.compile(
            "["
            "\U0001f600-\U0001f64f"  # emoticons
            "\U0001f300-\U0001f5ff"  # symbols & pictographs
            "\U0001f680-\U0001f6ff"  # transport & map symbols
            "\U0001f1e0-\U0001f1ff"  # flags (iOS)
            "\U00002702-\U000027b0"  # dingbats
            "\U000024c2-\U0001f251"
            "]+",
            flags=re.UNICODE,
        )
    )

    def model_post_init(self, __context: Any) -> None:
        """Initialize scorers after model validation."""
        super().model_post_init(__context)
        self._load_scorers()

    def _load_scorers(self) -> None:
        """Load all scorers with appropriate configurations."""
        # Load all scorers (both critical and advisory)
        all_scorers = self._critical_scorers | self._advisory_scorers

        for scorer_cls in all_scorers:
            scorer_params: dict[str, Any] = {
                "column_map": self.column_map,
                "device": self.device,
            }

            # Add specific threshold parameters based on scorer type
            if scorer_cls == WeaveContextRelevanceScorerV1:
                scorer_params["threshold"] = CONTEXT_RELEVANCE_SCORER_THRESHOLD
                scorer_params["model_name_or_path"] = (
                    self.context_relevance_model_name_or_path
                )
            elif scorer_cls == WeaveHallucinationScorerV1:
                scorer_params["threshold"] = HALLUCINATION_SCORER_THRESHOLD
                scorer_params["model_name_or_path"] = (
                    self.hallucination_model_name_or_path
                )
            elif scorer_cls == WeaveToxicityScorerV1:
                scorer_params["total_threshold"] = TOXICITY_TOTAL_THRESHOLD
                scorer_params["category_threshold"] = TOXICITY_CATEGORY_THRESHOLD
                scorer_params["model_name_or_path"] = self.toxicity_model_name_or_path
            elif scorer_cls == WeaveFluencyScorerV1:
                scorer_params["threshold"] = FLUENCY_SCORER_THRESHOLD
                scorer_params["model_name_or_path"] = self.fluency_model_name_or_path
            elif scorer_cls == WeaveCoherenceScorerV1:
                scorer_params["model_name_or_path"] = self.coherence_model_name_or_path

            # Initialize and store scorer
            self._loaded_scorers[scorer_cls.__name__] = scorer_cls(**scorer_params)

    def _preprocess_text(self, text: str) -> str:
        """Preprocess text by handling emojis and length."""
        if not text:
            return text

        # Replace emojis with their text representation while preserving spacing
        text = self._emoji_pattern.sub(lambda m: f" {m.group(0)} ", text)

        # Clean up multiple spaces and normalize whitespace
        text = " ".join(text.split())

        # Ensure proper sentence spacing
        text = (
            text.replace(" .", ".")
            .replace(" ,", ",")
            .replace(" !", "!")
            .replace(" ?", "?")
        )

        return text

    def _filter_inputs_for_scorer(
        self, scorer: weave.Scorer, inputs: dict[str, Any]
    ) -> dict[str, Any]:
        """Filter inputs to match scorer's signature."""
        scorer_params = signature(scorer.score).parameters
        return {k: v for k, v in inputs.items() if k in scorer_params}

    def _score_all(
        self,
        output: str,
        context: Union[str, list[str]],
        query: str,
    ) -> dict[str, Any]:
        """Run all applicable scorers and return their raw results."""
        # Preprocess inputs
        processed_output = self._preprocess_text(output)
        processed_context = (
            self._preprocess_text(context) if isinstance(context, str) else context
        )
        processed_query = self._preprocess_text(query) if query else None

        inputs: dict[str, Any] = {"output": processed_output}
        if processed_context is not None:
            inputs["context"] = processed_context
        if processed_query is not None:
            inputs["query"] = processed_query

        results = {}

        if self.run_in_parallel:
            with ThreadPoolExecutor() as executor:
                # Schedule each scorer's work concurrently.
                future_to_scorer = {
                    executor.submit(
                        scorer.score, **self._filter_inputs_for_scorer(scorer, inputs)
                    ): scorer_name
                    for scorer_name, scorer in self._loaded_scorers.items()
                }
                # Collect results as they complete.
                for future in as_completed(future_to_scorer):
                    scorer_name = future_to_scorer[future]
                    try:
                        results[scorer_name] = future.result()
                    except Exception as e:
                        raise WeaveTrustScorerError(
                            f"Error calling {scorer_name}: {e}", errors=e
                        )
        else:
            # Run scorers sequentially
            for scorer_name, scorer in self._loaded_scorers.items():
                try:
                    results[scorer_name] = scorer.score(
                        **self._filter_inputs_for_scorer(scorer, inputs)
                    )
                except Exception as e:
                    raise WeaveTrustScorerError(
                        f"Error calling {scorer_name}: {e}", errors=e
                    )

        return results

    def _score_with_logic(
        self,
        query: str,
        context: Union[str, list[str]],
        output: str,
    ) -> WeaveScorerResult:
        """Score with nuanced logic for trustworthiness."""
        raw_results = self._score_all(output=output, context=context, query=query)

        # Handle error case
        if "error" in raw_results:
            return raw_results["error"]

        # Track issues by type
        critical_issues = []
        advisory_issues = []

        # Check each scorer's results
        for scorer_name, result in raw_results.items():
            if not result.passed:
                scorer_cls = type(self._loaded_scorers[scorer_name])
                if scorer_cls in self._critical_scorers:
                    critical_issues.append(scorer_name)
                elif scorer_cls in self._advisory_scorers:
                    advisory_issues.append(scorer_name)

        # Determine trust level
        passed = True
        trust_level = "high_no-issues-found"
        if critical_issues:
            passed = False
            trust_level = "low_critical-issues-found"
        elif advisory_issues:
            trust_level = "medium_advisory-issues-found"

        # Extract scores where available
        scores = {}
        for name, result in raw_results.items():
            if name == "WeaveToxicityScorerV1":
                scores[name] = result.metadata  # Toxicity returns category scores
            elif hasattr(result, "metadata") and "score" in result.metadata:
                scores[name] = result.metadata["score"]

        return WeaveScorerResult(
            passed=passed,
            metadata={
                "trust_level": trust_level,
                "critical_issues": critical_issues,
                "advisory_issues": advisory_issues,
                "raw_outputs": raw_results,
                "scores": scores,
            },
        )

    @validate_call
    @weave.op
    def score(
        self,
        *,
        query: str,
        context: Union[str, list[str]],
        output: str,  # Pass the output of a LLM to this parameter for example
        **kwargs: Any,
    ) -> WeaveScorerResult:
        """
        Score the query, context and output against 5 different scorers.

        Args:
            query: str, The query to score the context against
            context: Union[str, list[str]], The context to score the query against
            output: str, The output to score, e.g. the output of a LLM
        """
        return self._score_with_logic(query=query, context=context, output=output)
