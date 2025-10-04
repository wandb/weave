"""Unified evaluation logger with automatic version selection.

This module provides a unified EvaluationLogger interface that automatically
selects between V1 and V2 implementations based on settings.
V2 (TraceServer-based) can be enabled via the WEAVE_USE_V2_EVAL_API environment variable.
"""

from __future__ import annotations

from weave.trace.settings import should_use_v2_eval_api

if should_use_v2_eval_api():
    from weave.evaluation.eval_imperative_v2 import (
        EvaluationLogger,
        ImperativeEvaluationLogger,
        ScoreLogger,
    )
else:
    from weave.evaluation.eval_imperative_v1 import (
        EvaluationLogger,
        ImperativeEvaluationLogger,
        ScoreLogger,
    )

__all__ = ["EvaluationLogger", "ImperativeEvaluationLogger", "ScoreLogger"]
