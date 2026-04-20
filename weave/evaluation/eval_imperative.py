"""EvaluationLogger dispatcher.

Dispatches at construction time to either the V1 or V2 implementation
based on ``weave.trace.settings.should_use_v2_eval_logger()`` (controlled
by the ``use_v2_eval_logger`` setting / ``WEAVE_USE_V2_EVAL_LOGGER`` env
var).

- V1: ``weave.evaluation.eval_imperative_v1``
- V2: ``weave.evaluation.eval_imperative_v2``

``EvaluationLogger`` and ``ScoreLogger`` are factory functions that
return an instance of the selected implementation. V1 and V2 are
independent classes sharing the same public API, so the return type is
a union of the two.
"""

from __future__ import annotations

import logging
from typing import Any

from weave.evaluation.eval_imperative_v1 import (
    DEFAULT_SCORER_CACHE_SIZE,
    IMPERATIVE_EVAL_MARKER,
    IMPERATIVE_SCORE_MARKER,
    ScorerCache,
    _LogScoreContext,
    current_output,
    current_predict_call,
    current_score,
    current_summary,
    global_scorer_cache,
)
from weave.evaluation.eval_imperative_v1 import EvaluationLogger as _V1EvaluationLogger
from weave.evaluation.eval_imperative_v1 import ScoreLogger as _V1ScoreLogger
from weave.evaluation.eval_imperative_v2 import EvaluationLogger as _V2EvaluationLogger
from weave.evaluation.eval_imperative_v2 import ScoreLogger as _V2ScoreLogger
from weave.flow.model import Model
from weave.flow.scorer import Scorer
from weave.trace import settings

logger = logging.getLogger(__name__)

AnyEvaluationLogger = _V1EvaluationLogger | _V2EvaluationLogger
AnyScoreLogger = _V1ScoreLogger | _V2ScoreLogger


def EvaluationLogger(*args: Any, **kwargs: Any) -> AnyEvaluationLogger:  # noqa: N802
    """Create an EvaluationLogger (V1 or V2 based on settings).

    See module docstring.
    """
    if settings.should_use_v2_eval_logger():
        return _V2EvaluationLogger(*args, **kwargs)
    return _V1EvaluationLogger(*args, **kwargs)


def ScoreLogger(*args: Any, **kwargs: Any) -> AnyScoreLogger:  # noqa: N802
    """Create a ScoreLogger (V1 or V2 based on settings).

    Most users obtain ScoreLoggers via ``EvaluationLogger.log_prediction``;
    this factory is exposed mainly for completeness.
    """
    if settings.should_use_v2_eval_logger():
        return _V2ScoreLogger(*args, **kwargs)
    return _V1ScoreLogger(*args, **kwargs)


def ImperativeEvaluationLogger(*args: Any, **kwargs: Any) -> AnyEvaluationLogger:  # noqa: N802
    """Legacy alias for EvaluationLogger."""
    logger.warning(
        "ImperativeEvaluationLogger was renamed to EvaluationLogger in 0.51.44"
        "Please use EvaluationLogger instead.  ImperativeEvaluationLogger will"
        "be removed in a future version."
    )
    return EvaluationLogger(*args, **kwargs)


__all__ = [
    "DEFAULT_SCORER_CACHE_SIZE",
    "IMPERATIVE_EVAL_MARKER",
    "IMPERATIVE_SCORE_MARKER",
    "EvaluationLogger",
    "ImperativeEvaluationLogger",
    "Model",
    "ScoreLogger",
    "Scorer",
    "ScorerCache",
    "_LogScoreContext",
    "current_output",
    "current_predict_call",
    "current_score",
    "current_summary",
    "global_scorer_cache",
]
