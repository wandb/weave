"""Pass/fail criteria for evaluation runs."""

from __future__ import annotations

import operator
from typing import Any, Literal

from pydantic import BaseModel


ComparisonOp = Literal[">=", "<=", ">", "<", "==", "!="]

_OP_MAP: dict[ComparisonOp, Any] = {
    ">=": operator.ge,
    "<=": operator.le,
    ">": operator.gt,
    "<": operator.lt,
    "==": operator.eq,
    "!=": operator.ne,
}


class EvaluationCriterion(BaseModel):
    """A single pass/fail condition applied to an aggregate scorer metric.

    Args:
        scorer (str): Name of the scorer whose summary to inspect.
        metric (str): Dot-separated path into the scorer's summary dict,
            e.g. ``"true_fraction"`` or ``"passed.true_fraction"``.
        op (ComparisonOp): Comparison operator.
        threshold (float): Value to compare the metric against.

    Examples:
        >>> c = EvaluationCriterion(scorer="exact_match", metric="true_fraction", op=">=", threshold=0.5)
        >>> c.scorer
        'exact_match'
    """

    scorer: str
    metric: str
    op: ComparisonOp
    threshold: float


class CriterionResult(BaseModel):
    """Outcome of evaluating a single criterion against a summary."""

    scorer: str
    metric: str
    op: str
    threshold: float
    actual: float | None
    passed: bool


class CriteriaResult(BaseModel):
    """Aggregate outcome of all criteria for an evaluation run."""

    passed: bool
    results: list[CriterionResult]


def _resolve_metric(summary: dict[str, Any], dot_path: str) -> float | None:
    """Walk a nested dict using a dot-separated path and return the leaf value.

    Args:
        summary (dict): The scorer summary dict.
        dot_path (str): Dot-separated key path, e.g. ``"passed.true_fraction"``.

    Returns:
        float | None: The resolved numeric value, or None if the path is invalid.

    Examples:
        >>> _resolve_metric({"passed": {"true_fraction": 0.75}}, "passed.true_fraction")
        0.75
        >>> _resolve_metric({"mean": 3.0}, "mean")
        3.0
        >>> _resolve_metric({}, "missing") is None
        True
    """
    current: Any = summary
    for key in dot_path.split("."):
        if not isinstance(current, dict) or key not in current:
            return None
        current = current[key]
    if isinstance(current, (int, float)):
        return float(current)
    return None


def evaluate_criteria(
    criteria: list[EvaluationCriterion],
    summary: dict[str, Any],
) -> CriteriaResult:
    """Evaluate all criteria against a completed evaluation summary.

    Args:
        criteria (list[EvaluationCriterion]): The criteria to check.
        summary (dict): The full evaluation summary dict (keyed by scorer name).

    Returns:
        CriteriaResult: Aggregate result with per-criterion details.

    Examples:
        >>> from weave.evaluation.criteria import EvaluationCriterion, evaluate_criteria
        >>> summary = {"my_scorer": {"true_fraction": 0.9}}
        >>> c = EvaluationCriterion(scorer="my_scorer", metric="true_fraction", op=">=", threshold=0.5)
        >>> evaluate_criteria([c], summary).passed
        True
    """
    results: list[CriterionResult] = []
    for criterion in criteria:
        scorer_summary = summary.get(criterion.scorer)
        if scorer_summary is None:
            results.append(
                CriterionResult(
                    scorer=criterion.scorer,
                    metric=criterion.metric,
                    op=criterion.op,
                    threshold=criterion.threshold,
                    actual=None,
                    passed=False,
                )
            )
            continue

        actual = _resolve_metric(scorer_summary, criterion.metric)
        if actual is None:
            passed = False
        else:
            cmp = _OP_MAP[criterion.op]
            passed = bool(cmp(actual, criterion.threshold))

        results.append(
            CriterionResult(
                scorer=criterion.scorer,
                metric=criterion.metric,
                op=criterion.op,
                threshold=criterion.threshold,
                actual=actual,
                passed=passed,
            )
        )

    return CriteriaResult(
        passed=all(r.passed for r in results),
        results=results,
    )
