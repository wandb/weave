"""Server-side dispatch contract for SDK evaluation workloads."""

from abc import ABC, abstractmethod

from weave.shared.trace_server_interface import EvaluateModelArgs

__all__ = ["EvaluateModelArgs", "EvaluateModelDispatcher"]


class EvaluateModelDispatcher(ABC):
    @abstractmethod
    def dispatch(self, args: EvaluateModelArgs) -> None:
        pass
