from abc import ABC, abstractmethod

from weave.evaluation.evaluate_model_worker import evaluate_model
from weave.trace_server.trace_server_interface import EvaluateModelArgs

# Re-exported for backward compatibility with downstream callers (e.g. the
# Kafka dispatcher in services/weave-trace) that historically imported
# EvaluateModelArgs from this module. The canonical definition now lives in
# trace_server_interface alongside RescoringArgs so both job types can share
# the EvalWorkerJob discriminated union. evaluate_model is re-exported for the
# same reason; it now lives in weave.evaluation.evaluate_model_worker.
__all__ = ["EvaluateModelArgs", "EvaluateModelDispatcher", "evaluate_model"]


class EvaluateModelDispatcher(ABC):
    @abstractmethod
    def dispatch(self, args: EvaluateModelArgs) -> None:
        pass
