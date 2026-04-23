"""Factory that returns an imperative evaluation logger (V1 or V2).

Public callers should use `weave.EvaluationLogger(...)`, which dispatches
through this factory. By default it returns the V1 `EvaluationLogger` so
existing users see no behavior change. Setting `use_evaluation_logger_v2`
(via `weave.init(settings={"use_evaluation_logger_v2": True})` or the
`WEAVE_USE_EVALUATION_LOGGER_V2` env var) switches the factory to the V2
implementation. V2 will become the default in a future release.

The concrete classes `EvaluationLogger` (V1) and `EvaluationLoggerV2` are
still importable directly from their modules for callers that want to pin
to a specific implementation.
"""

from __future__ import annotations

from typing import Any

from weave.evaluation._imperative_shared import EvaluationLoggerProtocol
from weave.evaluation.eval_imperative import EvaluationLogger as EvaluationLoggerV1
from weave.evaluation.eval_imperative_v2 import EvaluationLoggerV2
from weave.trace.settings import should_use_evaluation_logger_v2


def EvaluationLogger(*args: Any, **kwargs: Any) -> EvaluationLoggerProtocol:  # noqa: N802
    """Construct an imperative evaluation logger.

    Returns `EvaluationLoggerV2` when `use_evaluation_logger_v2` is set
    (via the settings object or `WEAVE_USE_EVALUATION_LOGGER_V2=true`);
    otherwise returns the V1 `EvaluationLogger`.
    """
    if should_use_evaluation_logger_v2():
        return EvaluationLoggerV2(*args, **kwargs)
    return EvaluationLoggerV1(*args, **kwargs)
