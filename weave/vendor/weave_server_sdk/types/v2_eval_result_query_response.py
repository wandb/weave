# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from typing import Dict, List, Optional
from typing_extensions import Literal

from pydantic import Field as FieldInfo

from .._models import BaseModel

__all__ = [
    "V2EvalResultQueryResponse",
    "Row",
    "RowEvaluation",
    "RowEvaluationTrial",
    "RowEvaluationTrialGenaiSpanRef",
    "Summary",
    "SummaryEvaluation",
    "SummaryEvaluationScorerStat",
]


class RowEvaluationTrialGenaiSpanRef(BaseModel):
    span_id: str

    trace_id: str


class RowEvaluationTrial(BaseModel):
    predict_and_score_call_id: str

    genai_span_ref: Optional[List[RowEvaluationTrialGenaiSpanRef]] = None

    api_model_latency_seconds: Optional[float] = FieldInfo(alias="model_latency_seconds", default=None)

    api_model_output: Optional[object] = FieldInfo(alias="model_output", default=None)

    predict_call_id: Optional[str] = None

    scorer_call_ids: Optional[Dict[str, str]] = None

    scores: Optional[Dict[str, object]] = None

    total_cost: Optional[float] = None

    total_tokens: Optional[int] = None


class RowEvaluation(BaseModel):
    evaluation_call_id: str

    trials: Optional[List[RowEvaluationTrial]] = None


class Row(BaseModel):
    row_digest: str

    evaluations: Optional[List[RowEvaluation]] = None

    raw_data_row: Optional[object] = None


class SummaryEvaluationScorerStat(BaseModel):
    """
    Stats for a single flattened score dimension (scorer_key or scorer_key.path.to.leaf).
    """

    scorer_key: str

    numeric_count: Optional[int] = None

    numeric_mean: Optional[float] = None

    pass_known_count: Optional[int] = None

    pass_rate: Optional[float] = None

    pass_signal_coverage: Optional[float] = None

    pass_true_count: Optional[int] = None

    path: Optional[str] = None
    """Dot-joined subpath for nested dimensions, e.g.

    'passed' for token_distance.passed. None for root-level scalar scorers.
    """

    trial_count: Optional[int] = None

    value_type: Optional[Literal["binary", "continuous", "text"]] = None
    """Type of the leaf value: binary (bool), continuous (number), or text (string)."""


class SummaryEvaluation(BaseModel):
    evaluation_call_id: str

    display_name: Optional[str] = None

    evaluation_ref: Optional[str] = None

    api_model_ref: Optional[str] = FieldInfo(alias="model_ref", default=None)

    predict_total_cost: Optional[float] = None
    """
    Sum of per-trial predict-only cost for this evaluation (the model's predict()
    cost only, excluding LLM-as-a-judge scorer cost); None when no trial reports
    cost.
    """

    predict_total_tokens: Optional[int] = None
    """
    Sum of per-trial predict-only token usage for this evaluation (the model's
    predict() tokens only, excluding LLM-as-a-judge scorer usage); None when no
    trial reports usage.
    """

    scorer_stats: Optional[List[SummaryEvaluationScorerStat]] = None

    started_at: Optional[str] = None

    trace_id: Optional[str] = None

    trial_count: Optional[int] = None


class Summary(BaseModel):
    evaluations: Optional[List[SummaryEvaluation]] = None

    row_count: Optional[int] = None


class V2EvalResultQueryResponse(BaseModel):
    rows: List[Row]

    total_rows: int

    summary: Optional[Summary] = None

    warnings: Optional[List[str]] = None
    """Non-fatal warnings (e.g. failed to resolve dataset row refs)."""
