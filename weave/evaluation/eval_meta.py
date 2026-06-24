"""Shared contract for the `_weave_eval_meta` call attribute.

Both evaluation paths (the declarative ``Evaluation.evaluate`` and the imperative
``EvaluationLogger``) tag their calls with this attribute so consumers — eval-results
rendering and a future server-side ingest sampler — can recognize and classify eval
calls. It lives in its own leaf module because ``eval_imperative`` imports ``eval``,
so neither can host a symbol the other needs without a circular import.
"""

from typing import TypedDict

# Call-attribute key under which evaluation metadata is stored.
EVAL_META_KEY = "_weave_eval_meta"


class EvalMeta(TypedDict, total=False):
    """Known fields under ``_weave_eval_meta``.

    All keys are optional and a call carries any subset. Callers (e.g.
    ``EvaluationLogger``) may also inject their own keys, so consumers must not
    assume the set is closed.
    """

    imperative: bool  # set on every call of the imperative path (EvaluationLogger)
    score: bool  # scorer call on the imperative path
    declarative: bool  # set on every child call of Evaluation.evaluate
    evaluate_model_worker: bool  # set by the eval-model worker
