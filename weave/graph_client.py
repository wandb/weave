import typing
from typing import Protocol, Generic, Sequence, TypeVar, Optional, Any
from abc import abstractmethod

from .ref_base import Ref
from .uris import WeaveURI
from .run import RunKey, Run

R = TypeVar("R", bound=Run)

if typing.TYPE_CHECKING:
    from .op_def import OpDef


class GraphClient(Protocol, Generic[R]):
    ##### Read API

    @abstractmethod
    def runs(self) -> Sequence[Run]:
        ...

    @abstractmethod
    def run(self, run_id: str) -> Optional[Run]:
        ...

    @abstractmethod
    def find_op_run(self, op_name: str, inputs: dict[str, Any]) -> Optional[Run]:
        ...

    @abstractmethod
    def run_children(self, run_id: str) -> Sequence[Run]:
        ...

    @abstractmethod
    def op_runs(self, op_def: "OpDef") -> Sequence[Run]:
        ...

    @abstractmethod
    def ref_input_to(self, ref: Ref) -> Sequence[Run]:
        ...

    @abstractmethod
    def ref_value_input_to(self, ref: Ref) -> Sequence[Run]:
        ...

    @abstractmethod
    def ref_output_of(self, ref: Ref) -> Optional[Run]:
        ...

    @abstractmethod
    def run_feedback(self, run_id: str) -> Sequence[dict[str, Any]]:
        ...

    @abstractmethod
    def feedback(self, feedback_id: str) -> Optional[dict[str, Any]]:
        ...

    ##### Helpers

    @abstractmethod
    def ref_is_own(self, ref: Optional[Ref]) -> bool:
        ...

    @abstractmethod
    def ref_uri(self, name: str, version: str, path: str) -> WeaveURI:
        ...

    @abstractmethod
    def run_ui_url(self, run: Run) -> str:
        ...

    ##### Write API

    @abstractmethod
    def save_object(self, obj: Any, name: str, branch_name: str) -> Ref:
        ...

    @abstractmethod
    def create_run(
        self,
        op_name: str,
        parent: Optional["RunKey"],
        inputs: dict[str, Any],
        input_refs: Sequence[Ref],
    ) -> R:
        ...

    @abstractmethod
    def fail_run(self, run: R, exception: BaseException) -> None:
        ...

    @abstractmethod
    def finish_run(self, run: R, output: Any, output_refs: Sequence[Ref]) -> None:
        ...

    @abstractmethod
    def add_feedback(self, run_id: str, feedback: dict[str, Any]) -> None:
        ...
