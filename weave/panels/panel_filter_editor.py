import dataclasses
import typing

import weave
from .. import panel
from .. import graph


ExpressionType = typing.TypeVar("ExpressionType")


@weave.type()
class FilterEditorConfig(typing.Generic[ExpressionType]):
    node: graph.Node[ExpressionType] = dataclasses.field(default_factory=graph.VoidNode)


@weave.type()
class FilterEditor(panel.Panel):
    id = "FilterEditor"
    config: FilterEditorConfig = dataclasses.field(default_factory=FilterEditorConfig)

    def __init__(
        self, input_node=graph.VoidNode(), vars=None, config=None, **options
    ) -> None:
        super().__init__(input_node=input_node, vars=vars)
        self.config = config
        if self.config is None:
            self.config = FilterEditorConfig()
        if "node" in options:
            self.config.node = options["node"]
