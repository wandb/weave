import dataclasses
import typing

from . import weave_types as types


class RunMetadata(typing.TypedDict):
    start_time_s: typing.Optional[float]
    end_time_s: typing.Optional[float]


def run_metadata() -> RunMetadata:
    return RunMetadata(
        start_time_s=None,
        end_time_s=None,
    )


@dataclasses.dataclass
class Run:
    id: str
    op_name: str
    state: str = dataclasses.field(default_factory=lambda: "pending")
    prints: list[str] = dataclasses.field(default_factory=list)
    history: list[dict] = dataclasses.field(default_factory=list)
    inputs: dict[str, typing.Any] = dataclasses.field(default_factory=dict)
    output: typing.Any = dataclasses.field(default_factory=lambda: None)
    metadata: RunMetadata = dataclasses.field(default_factory=run_metadata)


types.RunType.instance_classes = Run
types.RunType.instance_class = Run
