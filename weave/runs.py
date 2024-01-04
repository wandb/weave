import dataclasses
import typing

from . import weave_types as types
from . import uris
from . import ref_base


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

    def __repr__(self):
        friendly_op_name = self.op_name
        if "://" in self.op_name:
            op_uri = uris.WeaveURI.parse(friendly_op_name)
            friendly_op_name = op_uri.name + ":" + op_uri.version[:4]

        def format_value(v):
            if isinstance(v, ref_base.Ref):
                return f"<{v.name}:{v.version[:4]}>"
            else:
                return str(v)[:10] + "..."

        inputs = [v for k, v in self.inputs.items() if not k.startswith("_")]
        input_strings = [format_value(v) for v in inputs]
        param_string = ", ".join(input_strings)

        output_string = format_value(self.output)

        return (
            f"Run({self.id[:6]}): {friendly_op_name}({param_string}) -> {output_string}"
        )


types.RunType.instance_classes = Run
