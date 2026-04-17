"""EvaluationLogger dispatcher.

This module provides the public ``EvaluationLogger`` class and dispatches at
construction time to either the V1 or V2 implementation based on
``weave.trace.settings.should_use_v2_eval_logger()`` (controlled by the
``use_v2_eval_logger`` setting / ``WEAVE_USE_V2_EVAL_LOGGER`` env var).

- V1: ``weave.evaluation.eval_imperative_v1``
- V2: ``weave.evaluation.eval_imperative_v2``

The V1 and V2 implementations share the same public API. V2 additionally
persists evaluations via the V2 trace server APIs (``evaluation_create``,
``evaluation_run_create``, ``prediction_create``, ``score_create``,
``evaluation_run_finish``).
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


def _select_impl() -> type[_V1EvaluationLogger]:
    if settings.should_use_v2_eval_logger():
        return _V2EvaluationLogger
    return _V1EvaluationLogger


class EvaluationLogger:
    """Dispatching EvaluationLogger.

    Instantiating this class returns an instance of either the V1 or V2
    implementation depending on the ``use_v2_eval_logger`` setting.
    """

    def __new__(cls, *args: Any, **kwargs: Any) -> _V1EvaluationLogger:
        impl = _select_impl()
        return impl(*args, **kwargs)


class ScoreLogger:
    """Dispatching ScoreLogger.

    Instantiating this class returns an instance of either the V1 or V2
    implementation. Typically users obtain a ScoreLogger via
    ``EvaluationLogger.log_prediction(...)`` rather than constructing one
    directly; this class exists primarily for re-export and isinstance checks.
    """

    def __new__(cls, *args: Any, **kwargs: Any) -> _V1ScoreLogger:
        if settings.should_use_v2_eval_logger():
            return _V2ScoreLogger(*args, **kwargs)
        return _V1ScoreLogger(*args, **kwargs)


class ImperativeEvaluationLogger:
    """Legacy class name for EvaluationLogger.

    Maintained for backward compatibility. Please use EvaluationLogger.
    """

    def __new__(cls, *args: Any, **kwargs: Any) -> _V1EvaluationLogger:
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
