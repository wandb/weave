from abc import ABC, abstractmethod

from weave.shared.trace_server.trace_server_interface import EvaluateModelArgs


class EvaluateModelDispatcher(ABC):
    @abstractmethod
    def dispatch(self, args: EvaluateModelArgs) -> None:
        pass
