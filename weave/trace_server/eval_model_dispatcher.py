"""The server's seam for dispatching model-evaluation jobs.

The trace server depends only on this abstract ``EvaluateModelDispatcher``; the
concrete implementation (which runs evaluations in a subprocess with a live
WeaveClient — see ``weave.eval_worker``) is injected at runtime and lives in the
core repo. Keeping the seam in this client-free module lets the trace server
type its ``evaluate_model_dispatcher`` constructor parameter without importing
the client-coupled worker.
"""

from abc import ABC, abstractmethod

from weave.trace_server.trace_server_interface import EvaluateModelArgs


class EvaluateModelDispatcher(ABC):
    @abstractmethod
    def dispatch(self, args: EvaluateModelArgs) -> None:
        pass
