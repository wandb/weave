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
    genai_span_ref: Optional[List[RowEvaluationTrialGenaiSpanRef]] = None

    api_model_latency_seconds: Optional[float] = FieldInfo(alias="model_latency_seconds", default=None)

    api_model_output: object = FieldInfo(alias="model_output")

    predict_and_score_call_id: str

    predict_call_id: Optional[str] = None

    scorer_call_ids: Dict[str, str]

    scores: Dict[str, object]

    total_cost: Optional[float] = None

    total_tokens: Optional[int] = None


class RowEvaluation(BaseModel):
    evaluation_call_id: str

    trials: List[RowEvaluationTrial]


class Row(BaseModel):
    evaluations: List[RowEvaluation]

    raw_data_row: object

    row_digest: str


class SummaryEvaluationScorerStat(BaseModel):
    """
    Stats for a single flattened score dimension (scorer_key or scorer_key.path.to.leaf).
    """

    numeric_count: int

    numeric_mean: Optional[float] = None

    pass_known_count: int

    pass_rate: Optional[float] = None

    pass_signal_coverage: Optional[float] = None

    pass_true_count: int

    path: Optional[str] = None
    """Dot-joined subpath for nested dimensions, e.g.

    'passed' for token_distance.passed. None for root-level scalar scorers.
    """

    scorer_key: str

    trial_count: int

    value_type: Optional[Literal["binary", "continuous", "text"]] = None
    """Type of the leaf value: binary (bool), continuous (number), or text (string)."""


class SummaryEvaluation(BaseModel):
    display_name: Optional[str] = None

    evaluation_call_id: str

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

    scorer_stats: List[SummaryEvaluationScorerStat]

    started_at: Optional[str] = None

    trace_id: Optional[str] = None

    trial_count: int


class Summary(BaseModel):
    evaluations: List[SummaryEvaluation]

    row_count: int


class V2EvalResultQueryResponse(BaseModel):
    rows: List[Row]

    summary: Optional[Summary] = None

    total_rows: int

    warnings: List[str]
    """Non-fatal warnings (e.g. failed to resolve dataset row refs)."""
