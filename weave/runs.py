import dataclasses
import typing

from . import weave_types as types


@dataclasses.dataclass
class Run:
    id: str
    op_name: str
    state: str = dataclasses.field(default_factory=lambda: "pending")
    prints: list[str] = dataclasses.field(default_factory=list)
    history: list[dict[str, typing.Any]] = dataclasses.field(default_factory=list)
    inputs: dict[str, typing.Any] = dataclasses.field(default_factory=dict)
    output: typing.Any = dataclasses.field(default_factory=lambda: None)

    @property
    def trace_id(self) -> str:
        raise NotImplementedError

    @property
    def ui_url(self):
        return ""


types.RunType.instance_classes = Run
