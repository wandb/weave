import dataclasses
import typing

import weave
from .. import panel
from .. import graph


ExpressionType = typing.TypeVar("ExpressionType")


@weave.type()
class ExpressionEditorConfig(typing.Generic[ExpressionType]):
    expr: graph.Node[ExpressionType] = dataclasses.field(default_factory=graph.VoidNode)


@weave.type()
class ExpressionEditor(panel.Panel):
    id = "ExpressionEditor"
    config: ExpressionEditorConfig = dataclasses.field(
        default_factory=ExpressionEditorConfig
    )
