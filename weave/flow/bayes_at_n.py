"""Bayes@N posterior summaries for repeated binary scores."""

from __future__ import annotations

import math
from typing import Any, TypeAlias

from pydantic import Field, StrictInt, StrictStr, field_validator
from typing_extensions import Self

from weave.flow.casting import ScorerLike
from weave.flow.scorer import Scorer, apply_scorer_async
from weave.trace.box import unbox
from weave.trace.objectify import maybe_objectify, register_object
from weave.trace.op import op
from weave.trace.vals import WeaveObject

Identifier: TypeAlias = StrictStr | StrictInt


def _identifier_key(value: Any) -> tuple[type, str | int]:
    value = unbox(value)
    if type(value) not in {str, int}:
        raise ValueError("Question and trial IDs must be strings or integers.")
    return type(value), value


def _binary_score(value: Any) -> bool:
    value = unbox(value)
    if type(value) is bool:
        return value
    if type(value) is int and value in {0, 1}:
        return bool(value)
    raise ValueError("BayesAtNScorer requires a bool or integer 0/1 score.")


@register_object
class BayesAtNScorer(Scorer):
    """Wrap a binary scorer with fixed-question Bayes@N posterior summaries.

    Supply one dataset row per question/trial pair and use
    ``Evaluation(trials=1)``. Both declared ID lists must be nonempty and unique.
    The summary rejects missing or duplicate pairs and unscored rows. Automatic
    ``Evaluation(trials=N)`` repeats trial IDs and is unsupported for N > 1.
    An Evaluation with no scheduled rows does not invoke summaries and produces no Bayes@N result;
    calling this scorer's ``summarize([])`` directly raises ValueError.

    Each row supplies a ``scorer_inputs`` dictionary for the wrapped scorer.
    Its ``column_map`` and sync/async behavior are preserved. Use this wrapper's
    ``column_map`` to rename the question, trial, and scorer-input columns.
    The wrapped scorer must return a bool or integer 0/1. Set ``score_key`` to
    select such a value from a returned dictionary.

    The summary returns the posterior mean and posterior standard deviation of
    the mean correctness probability over the declared questions. Each question
    has a uniform Beta(1, 1) prior. These are exact posterior moments, conditional
    on the fixed questions and independent, comparable trials. Prior observations,
    categorical rubrics, and credible intervals are not supported.

    References:
        Hariri et al., Don't Pass@k: A Bayesian Framework for Large Language Model
        Evaluation, https://arxiv.org/abs/2510.04265.
        Reference: https://github.com/mohsenhariri/scorio/blob/7278f677c30396d99a0454bcbb08f5a9a53c4efb/scorio/eval/bayes.py.
    """

    scorer: ScorerLike
    question_ids: list[Identifier] = Field(min_length=1)
    trial_ids: list[Identifier] = Field(min_length=1)
    score_key: str | None = None

    @field_validator("question_ids", "trial_ids")
    @classmethod
    def validate_ids(cls, values: list[Identifier]) -> list[Identifier]:
        if len({_identifier_key(value) for value in values}) != len(values):
            raise ValueError("Question and trial ID lists must contain unique IDs.")
        return values

    @classmethod
    def from_obj(cls, obj: WeaveObject) -> Self:
        values = {
            field: getattr(obj, field)
            for field in cls.model_fields
            if hasattr(obj, field)
        }
        if isinstance(values.get("scorer"), WeaveObject):
            nested = maybe_objectify(values["scorer"])
            if isinstance(nested, WeaveObject):
                raise TypeError(
                    "The wrapped scorer class must be registered to reload its object."
                )
            values["scorer"] = nested
        return cls(**values)

    @op
    async def score(
        self,
        *,
        output: Any,
        question_id: Any = None,
        trial_id: Any = None,
        scorer_inputs: Any = None,
        **kwargs: Any,
    ) -> Any:
        """Score a generation using its explicit grader inputs and retain both IDs."""
        question_id = _identifier_key(question_id)[1]
        trial_id = _identifier_key(trial_id)[1]
        if not isinstance(scorer_inputs, dict):
            raise TypeError(
                "scorer_inputs must be a dictionary for the wrapped scorer."
            )
        result = (await apply_scorer_async(self.scorer, scorer_inputs, output)).result
        if self.score_key is not None:
            if not isinstance(result, dict) or self.score_key not in result:
                raise ValueError("The wrapped scorer result is missing score_key.")
            result = result[self.score_key]
        return {
            "question_id": question_id,
            "trial_id": trial_id,
            "correct": _binary_score(result),
        }

    @op
    def summarize(self, score_rows: list) -> dict | None:
        """Return exact binary posterior moments after checking the full cohort."""
        question_keys = {_identifier_key(value) for value in self.question_ids}
        trial_keys = {_identifier_key(value) for value in self.trial_ids}
        if (
            not question_keys
            or not trial_keys
            or len(question_keys) != len(self.question_ids)
            or len(trial_keys) != len(self.trial_ids)
        ):
            raise ValueError("Question and trial ID lists must be nonempty and unique.")
        if len(score_rows) != len(question_keys) * len(trial_keys):
            raise ValueError(
                "Bayes@N requires the complete declared question/trial cohort."
            )
        successes = dict.fromkeys(question_keys, 0)
        seen = set()
        for row in score_rows:
            if not isinstance(row, dict) or set(row) != {
                "question_id",
                "trial_id",
                "correct",
            }:
                raise ValueError("Bayes@N requires a scored result for every trial.")
            question_key = _identifier_key(row["question_id"])
            trial_key = _identifier_key(row["trial_id"])
            if question_key not in question_keys or trial_key not in trial_keys:
                raise ValueError(
                    "Score rows contain an undeclared question or trial ID."
                )
            pair = question_key, trial_key
            if pair in seen:
                raise ValueError("Score rows contain a duplicate question/trial pair.")
            seen.add(pair)
            successes[question_key] += _binary_score(row["correct"])

        questions = len(question_keys)
        total = len(trial_keys) + 2
        means = [(count + 1) / total for count in successes.values()]
        variances = [mean * (1 - mean) / (total + 1) for mean in means]
        return {
            "posterior_mean": math.fsum(means) / questions,
            "posterior_sd": math.sqrt(math.fsum(variances)) / questions,
        }
