import dataclasses
import typing

import weave
from .. import panel
from .. import graph


ExpressionType = typing.TypeVar("ExpressionType")


@weave.type()
class GroupingEditorConfig(typing.Generic[ExpressionType]):
    node: graph.Node[ExpressionType] = dataclasses.field(default_factory=graph.VoidNode)


@weave.type()
class GroupingEditor(panel.Panel):
    id = "GroupingEditor"
    config: GroupingEditorConfig = dataclasses.field(
        default_factory=GroupingEditorConfig
    )

    def __init__(
        self, input_node=graph.VoidNode(), vars=None, config=None, **options
    ) -> None:
        super().__init__(input_node=input_node, vars=vars)
        self.config = config
        if self.config is None:
            self.config = GroupingEditorConfig()
        if "node" in options:
            self.config.node = options["node"]
