# Was putting in these midpoint functions, but date-add and some other
# date functions don't have arrow equivalents yet, so these don't vectorize

import typing

import weave

from .. import panels
from .. import weave_internal
from ..panels import panel_facet


@weave.type()
class ConfusionMatrixConfig:
    x: str
    y: str


@weave.type()
class ConfusionMatrix(weave.Panel):
    id = "ConfusionMatrix"
    input_node: weave.Node[list[typing.Any]]
    config: typing.Optional[ConfusionMatrixConfig] = None

    @weave.op()
    def initialize(self) -> ConfusionMatrixConfig:
        return ConfusionMatrixConfig(x='truth', y='guess')

    @weave.op()
    def render_config(self) -> panels.Panel:
        self_var = weave_internal.make_var_node(weave.type_of(self), "self")
        return panels.Dropdown(
            self_var.config.x, choices=weave_internal.const(['guess', 'truth'])
        )

    @weave.op()
    def render(self) -> panels.Panel:
        return panel_facet.Facet(self.input_node, 
                                 x=lambda i: i[self.config.x],
                                 y=lambda i: i[self.config.x])


# Was putting in these midpoint functions, but date-add and some other
# date functions don't have arrow equivalents yet, so these don't vectorize

import typing

import weave

from .. import panels
from .. import weave_internal
from ..panels import panel_facet
from ..panels import panel_table


@weave.type()
class ConfusionMatrixConfig:
    x: str
    y: str


@weave.type()
class ConfusionMatrix(weave.Panel):
    id = "ConfusionMatrix"
    input_node: weave.Node[list[typing.Any]]
    config: typing.Optional[ConfusionMatrixConfig] = None

    @weave.op()
    def initialize(self) -> ConfusionMatrixConfig:
        return ConfusionMatrixConfig(x='truth', y='guess')

    @weave.op()
    def render_config(self) -> panels.Panel:
        self_var = weave_internal.make_var_node(weave.type_of(self), "self")
        return weave.panels.Group(
            items={
                "x": panels.Dropdown(
                        self_var.config.x, choices=self.input_node[0].keys()
                    ),
                "y": panels.Dropdown(
                        self_var.config.y, choices=self.input_node[0].keys(),
                )
            }
        )

    @weave.op()
    def render(self) -> panels.Panel:
        return weave.panels.Group(
                    equalSize=True,
                    preferHorizontal=True,
                    items={
            'confusion': weave.panels.Facet(
                             self.input_node,
                             x=lambda row: row[self.config.x],
                             y=lambda row: row[self.config.y],
                             select=lambda row: weave.panels.Group(
                                 layoutMode='layer',
                                 items={
                                     'count': weave.panels.PanelNumber(row.count()),
                                 }
                             )
                        ),
            'selected': lambda confusion: confusion.selected()
        }
    )


# from .. import graph
# import typing
# import weave
# from . import panel_group, panel_facet, panel_function_editor, panel_labeled_item
# from .. import panel
# import dataclasses

# @weave.type()
# class ConfusionMatrixConfig:
#     x_fn: weave.Node[typing.Optional[typing.Any]] = dataclasses.field(
#         default_factory=lambda: weave.graph.VoidNode()
#     )
#     y_fn: weave.Node[typing.Optional[typing.Any]] = dataclasses.field(
#         default_factory=lambda: weave.graph.VoidNode()
#     )

# @weave.type()
# class ConfusionMatrix(panel.Panel):
#     id = "ConfusionMatrix"
#     input_node: weave.Node[list[typing.Any]]
#     config: typing.Optional[panel_facet.FacetConfig] = None

#     def __init__(self, input_node, vars=None, config=None, **options):
#         super().__init__(input_node=input_node, vars=vars)
#         facet = panel_facet.Facet(self.input_node, config=self.config)
#         x_fn = facet.config.table.columnSelectFunctions['truth']
#         self.config = config
#         if self.config is None:
#             self.config = ConfusionMatrixConfig(
#                 x_fn=weave.define_fn({"item": x_fn}, lambda item: item),
#                 y_fn=weave.define_fn({"item": x_fn}, lambda item: item),
#             )

#     @weave.op()
#     def render(self) -> panel_facet.Facet:
#         return panel_facet.Facet(self.input_node, config=self.config)

#     @weave.op()
#     def render_config(self) -> panel_group.Group:
#         config = typing.cast(ConfusionMatrixConfig, self.config)
#         return panel_group.Group(
#             items={
#                 "x_fn": panel_labeled_item.LabeledItem(
#                     label="x", item=panel_function_editor.FunctionEditor(config.x_fn)
#                 ),
#                 "y_fn": panel_labeled_item.LabeledItem(
#                     label="y", item=panel_function_editor.FunctionEditor(config.y_fn)
#                 )
#             }
#         )

# from .. import graph
# import typing
# import weave
# from . import panel_group, panel_facet, panel_function_editor, panel_labeled_item
# from .. import panel
# import dataclasses

# @weave.type()
# class ConfusionMatrixConfig:
#     x_fn: weave.Node[typing.Optional[typing.Any]] = dataclasses.field(
#         default_factory=lambda: weave.graph.VoidNode()
#     )
#     y_fn: weave.Node[typing.Optional[typing.Any]] = dataclasses.field(
#         default_factory=lambda: weave.graph.VoidNode()
#     )

# @weave.type()
# class ConfusionMatrix(panel.Panel):
#     id = "ConfusionMatrix"
#     input_node: weave.Node[list[typing.Any]]
#     config: typing.Optional[panel_facet.FacetConfig] = None

#     def __init__(self, input_node, vars=None, config=None, **options):
#         super().__init__(input_node=input_node, vars=vars)
#         facet = panel_facet.Facet(self.input_node, config=self.config)
#         x_fn = facet.config.table.columnSelectFunctions['truth']
#         self.config = config
#         if self.config is None:
#             self.config = ConfusionMatrixConfig(
#                 x_fn=weave.define_fn({"item": x_fn}, lambda item: item),
#                 y_fn=weave.define_fn({"item": x_fn}, lambda item: item),
#             )

#     @weave.op()
#     def render(self) -> panel_facet.Facet:
#         return panel_facet.Facet(self.input_node, config=self.config)

#     @weave.op()
#     def render_config(self) -> panel_group.Group:
#         config = typing.cast(ConfusionMatrixConfig, self.config)
#         return panel_group.Group(
#             items={
#                 "x_fn": panel_labeled_item.LabeledItem(
#                     label="x", item=panel_function_editor.FunctionEditor(config.x_fn)
#                 ),
#                 "y_fn": panel_labeled_item.LabeledItem(
#                     label="y", item=panel_function_editor.FunctionEditor(config.y_fn)
#                 )
#             }
#         )
