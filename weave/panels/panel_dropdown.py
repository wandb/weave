import dataclasses
import typing

import weave
from .. import panel
from .. import weave_internal
from .. import graph


@weave.type()
class DropdownConfig:
    choices: weave.Node[list[str]] = dataclasses.field(
        default_factory=lambda: graph.VoidNode()
    )


@weave.type()
class Dropdown(panel.Panel):
    id = "Dropdown"
    config: typing.Optional[DropdownConfig] = dataclasses.field(
        default_factory=DropdownConfig
    )

    def __init__(
        self, input_node=graph.VoidNode(), vars=None, config=None, **options
    ) -> None:
        super().__init__(input_node=input_node, vars=vars)
        self.config = config
        if self.config is None:
            self.config = DropdownConfig()
        if "choices" in options:
            self.config.choices = options["choices"]
        if isinstance(self.input_node, weave.graph.VoidNode):
            choices_type = typing.cast(weave.types.List, self.config.choices.type)
            self.input_node = weave_internal.const(
                [], weave.types.List(choices_type.object_type)
            )

    @weave.op()
    def value(self) -> float:
        return weave.use(self.input_node)
