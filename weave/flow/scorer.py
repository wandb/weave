import inspect
import textwrap
from collections.abc import Sequence
from dataclasses import dataclass
from numbers import Number
from typing import Any, Callable, Optional, Union, cast

import numpy as np
from pydantic import BaseModel, Field
from typing_extensions import Self

from weave.flow.obj import Object
from weave.trace.isinstance import weave_isinstance
from weave.trace.op import Op, as_op, is_op, op
from weave.trace.util import sanitize_object_name
from weave.trace.vals import WeaveObject


class Scorer(Object):
    column_map: Optional[dict[str, str]] = Field(
        default=None,
        description="A mapping from column names in the dataset to the names expected by the scorer",
    )

    def model_post_init(self, __context: Any) -> None:
        super().model_post_init(__context)
        _validate_scorer_signature(self)

    @op
    def score(self, *, output: Any, **kwargs: Any) -> Any:
        raise NotImplementedError

    @op
    def summarize(self, score_rows: list) -> Optional[dict]:
        return auto_summarize(score_rows)


class BuiltInScorer(Scorer):
    @classmethod
    def from_obj(cls, obj: WeaveObject) -> Self:
        field_values = {}
        for field_name in cls.model_fields:
            if hasattr(obj, field_name):
                field_values[field_name] = getattr(obj, field_name)

        return cls(**field_values)


def _validate_scorer_signature(scorer: Union[Callable, Op, Scorer]) -> bool:
    """Validate that the scorer signature does not have both `output` and `model_output`.

    Having both `output` and `model_output` in the scorer signature causes
    issues with scoring because it's ambigious as to which one is the
    canonical "output", and which is just a regular kwarg.
    """
    if isinstance(scorer, Scorer):
        params = inspect.signature(scorer.score).parameters
    else:
        params = inspect.signature(scorer).parameters
    if "output" in params and "model_output" in params:
        raise ValueError(
            textwrap.dedent(
                """
                The scorer signature cannot include both `output` and `model_output` at the same time.

                To resolve, rename one of the arguments to avoid conflict. Prefer using `output` as the model's output.
                """
            )
        )
    return True


def stderr(data: Sequence[Union[int, float]]) -> float:
    if len(data) > 1:
        sample_variance = np.var(data, ddof=1)
        return float(np.sqrt(sample_variance / len(data)))
    else:
        return 0


def auto_summarize(data: list) -> Optional[dict[str, Any]]:
    """Automatically summarize a list of (potentially nested) dicts.

    Computes:
        - avg for numeric cols
        - count and fraction for boolean cols
        - other col types are ignored

    If col is all None, result is None

    Returns:
      dict of summary stats, with structure matching input dict structure.
    """
    if not data:
        return {}
    data = [x for x in data if x is not None]

    if not data:
        return None

    val = data[0]

    if isinstance(val, bool):
        return {
            "true_count": (true_count := sum(1 for x in data if x)),
            "true_fraction": true_count / len(data),
        }
    elif isinstance(val, Number):
        return {"mean": np.mean(data).item()}
    elif isinstance(val, dict):
        result = {}
        all_keys = set().union(*[x.keys() for x in data if isinstance(x, dict)])
        for k in all_keys:
            if (
                summary := auto_summarize(
                    [x.get(k) for x in data if isinstance(x, dict)]
                )
            ) is not None:
                if k in summary:
                    result.update(summary)
                else:
                    result[k] = summary
        if not result:
            return None
        return result
    elif isinstance(val, BaseModel):
        return auto_summarize([x.model_dump() for x in data])
    return None


@dataclass
class ScorerAttributes:
    scorer_name: str
    score_op: Op
    summarize_fn: Callable


def get_scorer_attributes(
    scorer: Union[Op, Scorer],
) -> ScorerAttributes:
    score_op: Op
    scorer_name: str
    if weave_isinstance(scorer, Scorer):
        if scorer.name:
            scorer_name = scorer.name
        else:
            scorer_name = scorer.__class__.__name__
        try:
            if not is_op(scorer.score):
                raise TypeError(
                    f"Scorer {scorer_name} must implement `score` as a weave.op() decorated function."
                )
            score_op = scorer.score
            summarize_fn = scorer.summarize  # type: ignore

        except AttributeError:
            raise ValueError(
                f"Scorer {scorer_name} must implement score and summarize methods. Did you forget to wrap with @weave.op()?"
            )
    elif is_op(scorer):
        scorer = as_op(scorer)
        scorer_name = cast(str, scorer.name)
        score_op = scorer
        summarize_fn = auto_summarize  # type: ignore
    else:
        raise ValueError(f"Unknown scorer type: {scorer}")

    if scorer_name:
        scorer_name = sanitize_object_name(scorer_name)

    return ScorerAttributes(
        scorer_name=scorer_name, score_op=score_op, summarize_fn=summarize_fn
    )


def _has_oldstyle_scorers(scorers: list[Union[Op, Scorer]]) -> bool:
    """Check if any scorers use the deprecated 'model_output' parameter."""
    for scorer in scorers:
        scorer_attributes = get_scorer_attributes(scorer)
        score_op = scorer_attributes.score_op
        score_signature = inspect.signature(score_op)
        if "model_output" in score_signature.parameters:
            return True
    return False


class WeaveScorerResult(BaseModel):
    """The result of a weave.Scorer.score method."""

    passed: bool = Field(description="Whether the scorer passed or not")
    metadata: dict[str, Any] = Field(
        description="Any extra information from the scorer like numerical scores, model outputs, etc."
    )
