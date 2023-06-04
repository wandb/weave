import dataclasses
import typing

import weave
from .. import panel
from .. import weave_internal
from .. import graph


@weave.type()
class SelectEditorConfig:
    choices: weave.Node[list[str]] = dataclasses.field(
        default_factory=lambda: graph.VoidNode()
    )


@weave.type()
class SelectEditor(panel.Panel):
    id = "SelectEditor"
    config: typing.Optional[SelectEditorConfig] = dataclasses.field(
        default_factory=SelectEditorConfig
    )

    def __init__(self, input_node=graph.VoidNode(), vars=None, config=None, **options):
        super().__init__(input_node=input_node, vars=vars)
        self.config = config
        if self.config is None:
            self.config = SelectEditorConfig()
        if "choices" in options:
            self.config.choices = options["choices"]
        if isinstance(self.input_node, weave.graph.VoidNode):
            # TODO: not string!
            self.input_node = weave_internal.const(
                [], weave.types.List(self.config.choices.type.object_type)
            )

    @weave.op()
    def value(self) -> float:
        return weave.use(self.input_node)
