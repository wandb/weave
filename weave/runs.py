import dataclasses
import typing

from . import weave_types as types


@dataclasses.dataclass
class Run:
    id: str
    op_name: str
    state: str = dataclasses.field(default_factory=lambda: "pending")
    prints: list[str] = dataclasses.field(default_factory=list)
    history: list[dict] = dataclasses.field(default_factory=list)
    inputs: dict[str, typing.Any] = dataclasses.field(default_factory=dict)
    output: typing.Any = dataclasses.field(default_factory=lambda: None)


types.RunType.instance_classes = Run
types.RunType.instance_class = Run
