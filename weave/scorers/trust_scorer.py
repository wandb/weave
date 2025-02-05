"""
W&B Trust Score implementation.

This scorer combines multiple scorers to provide a comprehensive trust evaluation.
"""

import re
from typing import Optional, Union, Any, Dict, Set, Type
from concurrent.futures import ThreadPoolExecutor, as_completed
from inspect import signature

import weave
from weave.scorers.base_scorer import Scorer
from weave.scorers import (
    HallucinationScorer, 
    CoherenceScorer, 
    FluencyScorer, 
    ContextRelevanceScorer, 
    ToxicityScorer
)
from pydantic import PrivateAttr, Field


class TrustScorer(Scorer):
    """A comprehensive trust evaluation scorer that combines multiple specialized scorers.

    The TrustScorer evaluates the trustworthiness of model outputs by combining multiple
    specialized scorers into two categories:

    1. Critical Scorers (automatic failure if flagged):
        - ToxicityScorer: Detects harmful, offensive, or inappropriate content
        - HallucinationScorer: Identifies fabricated or unsupported information
        - ContextRelevanceScorer: Ensures output relevance to provided context

    2. Advisory Scorers (warnings that may affect trust):
        - FluencyScorer: Evaluates language quality and coherence
        - CoherenceScorer: Checks for logical consistency and flow

    Trust Levels:
        - "high": No issues detected
        - "medium": Only advisory issues detected
        - "low": Critical issues detected or empty input

    Args:
        device (str): Device for model inference ("cpu", "cuda", "mps", "auto"). Defaults to "auto".
        context_relevance_threshold (float): Minimum relevance score (0-1). Defaults to 0.45.
        hallucination_threshold (float): Maximum hallucination score (0-1). Defaults to 0.5.
        fluency_threshold (float): Minimum fluency score (0-1). Defaults to 0.5.
        toxicity_total_threshold (int): Maximum total toxicity score. Defaults to 5.
        toxicity_category_threshold (int): Maximum per-category toxicity score. Defaults to 2.
        run_in_parallel (bool): Flag to toggle parallel scoring. Defaults to True.

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
        {
            "flagged": False,
            "trust_level": "high",
            "extras": {
                "raw_outputs": {
                    "ToxicityScorer": {"flagged": False, "extras": {"score": 0}},
                    "HallucinationScorer": {"flagged": False, "extras": {"score": 0.1}},
                    "ContextRelevanceScorer": {"flagged": False, "extras": {"score": 0.85}},
                    "FluencyScorer": {"flagged": False, "extras": {"score": 0.95}},
                    "CoherenceScorer": {"flagged": False, "extras": {"score": 0.9}}
                },
                "scores": {
                    "ToxicityScorer": 0,
                    "HallucinationScorer": 0.1,
                    "ContextRelevanceScorer": 0.85,
                    "FluencyScorer": 0.95,
                    "CoherenceScorer": 0.9
                }
            }
        }
        ```

    """
    # Model configuration
    device: str = Field(
        default="auto",
        description="Device for model inference ('cpu', 'cuda', 'mps', 'auto')"
    )
    context_relevance_threshold: float = Field(
        default=0.45,
        description="Minimum relevance score between output and context (0-1)"
    )
    hallucination_threshold: float = Field(
        default=0.5,
        description="Maximum hallucination score allowed in output (0-1)"
    )
    fluency_threshold: float = Field(
        default=0.5,
        description="Minimum fluency score required for output (0-1)"
    )
    toxicity_total_threshold: int = Field(
        default=5,
        description="Maximum total toxicity score allowed across all categories"
    )
    toxicity_category_threshold: int = Field(
        default=2,
        description="Maximum toxicity score allowed per individual category"
    )
    context_relevance_model_name_or_path: str = Field(
        default="",
        description="Path or name of the context relevance model",
        validate_default=True
    )
    hallucination_model_name_or_path: str = Field(
        default="",
        description="Path or name of the hallucination model",
        validate_default=True
    )
    toxicity_model_name_or_path: str = Field(
        default="",
        description="Path or name of the toxicity model",
        validate_default=True
    )
    fluency_model_name_or_path: str = Field(
        default="",
        description="Path or name of the fluency model",
        validate_default=True
    )
    coherence_model_name_or_path: str = Field(
        default="",
        description="Path or name of the coherence model",
        validate_default=True
    )
    run_in_parallel: bool = Field(
        default=True,
        description="Whether to run scorers in parallel for improved performance"
    )

    # Define scorer categories
    _critical_scorers: Set[Type[Scorer]] = {
        ToxicityScorer, 
        HallucinationScorer, 
        ContextRelevanceScorer
    }
    _advisory_scorers: Set[Type[Scorer]] = {
        FluencyScorer, 
        CoherenceScorer
    }
    
    # Private attributes
    _loaded_scorers: Dict[str, Scorer] = PrivateAttr(default_factory=dict)
    _emoji_pattern: re.Pattern = PrivateAttr(default=re.compile(
        "["
        "\U0001F600-\U0001F64F"  # emoticons
        "\U0001F300-\U0001F5FF"  # symbols & pictographs
        "\U0001F680-\U0001F6FF"  # transport & map symbols
        "\U0001F1E0-\U0001F1FF"  # flags (iOS)
        "\U00002702-\U000027B0"  # dingbats
        "\U000024C2-\U0001F251" 
        "]+", 
        flags=re.UNICODE
    ))

    def model_post_init(self, __context: Any) -> None:
        """Initialize scorers after model validation."""
        super().model_post_init(__context)
        self._load_scorers()

    def _load_scorers(self) -> None:
        """Load all scorers with appropriate configurations."""
        base_params = {
            'column_map': self.column_map,
            'device': self.device,
        }
        
        # Load all scorers (both critical and advisory)
        all_scorers = self._critical_scorers | self._advisory_scorers
        
        for scorer_cls in all_scorers:
            scorer_params = base_params.copy()
            
            # Add specific threshold parameters based on scorer type
            if scorer_cls == ContextRelevanceScorer:
                scorer_params['threshold'] = self.context_relevance_threshold
                scorer_params["model_name_or_path"] = self.context_relevance_model_name_or_path
            elif scorer_cls == HallucinationScorer:
                scorer_params['threshold'] = self.hallucination_threshold
                scorer_params["model_name_or_path"] = self.hallucination_model_name_or_path
            elif scorer_cls == ToxicityScorer:
                scorer_params['total_threshold'] = self.toxicity_total_threshold
                scorer_params['category_threshold'] = self.toxicity_category_threshold
                scorer_params["model_name_or_path"] = self.toxicity_model_name_or_path
            elif scorer_cls == FluencyScorer:
                scorer_params['threshold'] = self.fluency_threshold
                scorer_params["model_name_or_path"] = self.fluency_model_name_or_path
            elif scorer_cls == CoherenceScorer:
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
        text = ' '.join(text.split())
        
        # Ensure proper sentence spacing
        text = text.replace(' .', '.').replace(' ,', ',').replace(' !', '!').replace(' ?', '?')
            
        return text

    def _validate_input(self, output: str) -> Optional[Dict[str, Any]]:
        """Validate input and return error response if invalid."""
        if not output or not output.strip():
            return {
                "flagged": False,
                "trust_level": "low",
                "critical_issues": ["EmptyInput"],
                "advisory_issues": [],
                "extras": {
                    "error": "Empty input provided",
                    "raw_outputs": {},
                    "scores": {}
                }
            }
        return None

    def _filter_inputs_for_scorer(self, scorer: Scorer, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """Filter inputs to match scorer's signature."""
        scorer_params = signature(scorer.score).parameters
        return {k: v for k, v in inputs.items() if k in scorer_params}

    def _score_all(
        self, 
        output: str, 
        context: Optional[Union[str, list[str]]] = None, 
        query: Optional[str] = None
    ) -> Dict[str, Any]:
        """Run all applicable scorers and return their raw results.

        Runs in parallel if run_in_parallel is True, otherwise runs sequentially.
        """
        # Validate input
        error_response = self._validate_input(output)
        if error_response:
            return {"error": error_response}
    
        # Preprocess inputs
        processed_output = self._preprocess_text(output)
        processed_context = self._preprocess_text(context) if isinstance(context, str) else context
        processed_query = self._preprocess_text(query) if query else None
    
        inputs = {'output': processed_output}
        if processed_context is not None:
            inputs['context'] = processed_context
        if processed_query is not None:
            inputs['query'] = processed_query
        
        results = {}

        if self.run_in_parallel:
            with ThreadPoolExecutor() as executor:
                # Schedule each scorer's work concurrently.
                future_to_scorer = {
                    executor.submit(scorer.score, **self._filter_inputs_for_scorer(scorer, inputs)): scorer_name
                    for scorer_name, scorer in self._loaded_scorers.items()
                }
                # Collect results as they complete.
                for future in as_completed(future_to_scorer):
                    scorer_name = future_to_scorer[future]
                    try:
                        results[scorer_name] = future.result()
                    except Exception:
                        # Silently skip failed scorers.
                        pass
        else:
            # Run scorers sequentially
            for scorer_name, scorer in self._loaded_scorers.items():
                try:
                    results[scorer_name] = scorer.score(**self._filter_inputs_for_scorer(scorer, inputs))
                except Exception:
                    pass
        
        return results

    def _score_with_logic(
        self, 
        output: str, 
        context: Optional[Union[str, list[str]]] = None, 
        query: Optional[str] = None
    ) -> Dict[str, Any]:
        """Score with nuanced logic for trustworthiness."""
        # Validate input
        error_response = self._validate_input(output)
        if error_response:
            return error_response

        raw_results = self._score_all(output=output, context=context, query=query)
        
        # Handle error case
        if "error" in raw_results:
            return raw_results["error"]
        
        # Track issues by type
        critical_issues = []
        advisory_issues = []
        
        # Check each scorer's results
        for scorer_name, result in raw_results.items():
            if result.get("flagged", False):
                scorer_cls = type(self._loaded_scorers[scorer_name])
                if scorer_cls in self._critical_scorers:
                    critical_issues.append(scorer_name)
                elif scorer_cls in self._advisory_scorers:
                    advisory_issues.append(scorer_name)
        
        # Determine trust level
        trust_level = "high"
        if critical_issues:
            trust_level = "low"
        elif advisory_issues:
            trust_level = "medium"
        
        # Extract scores where available
        scores = {
            name: result["extras"]["score"]
            for name, result in raw_results.items()
            if "extras" in result and "score" in result["extras"]
        }
        
        for i, label in enumerate(raw_results["FluencyScorer"]["extras"]):
            if label == "non_fluent_score":
                scores["FluencyScorer"] = raw_results["FluencyScorer"]["extras"][i]["score"]
        
        scores["ToxicityScorer"] = raw_results["ToxicityScorer"]["extras"]
        
        return {
            "flagged": bool(critical_issues),
            "trust_level": trust_level,
            "critical_issues": critical_issues,
            "advisory_issues": advisory_issues,
            "extras": {
                "raw_outputs": raw_results,
                "scores": scores
            }
        }

    @weave.op
    def score(
        self, 
        query: Optional[str] = None,
        context: Optional[Union[str, list[str]]] = None, 
        output: Optional[str] = None
    ) -> Dict[str, Any]:
        """Basic scoring that flags any issues."""
        result = self._score_with_logic(output=output, context=context, query=query)
        return {
            "flagged": result["flagged"],
            "extras": {
                "trust_level": result["trust_level"],
                "raw_outputs": result["extras"]["raw_outputs"],
                "scores": result["extras"]["scores"]
            }
        }
