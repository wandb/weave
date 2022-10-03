import dataclasses
import typing

import weave
from .. import weave_internal
from .. import panel


ChoiceType = typing.TypeVar("ChoiceType", bound=weave.Node)


@weave.type()
class PanelObjectPickerConfig(typing.Generic[ChoiceType]):
    choice: ChoiceType = dataclasses.field(default_factory=weave.graph.VoidNode)


@weave.type()
class ObjectPicker(panel.Panel):
    id = "ObjectPicker"
    config: PanelObjectPickerConfig = dataclasses.field(
        default_factory=PanelObjectPickerConfig
    )

    def __post_init__(self):
        # Set choice to a VarNode of the correct type (an item in our input
        # list). This ensures that ObjectPickers stored in variables have a
        # choice attribute that can be correctly dot-chained. Ie we want
        # to maintain that the type is always correct.
        self.config.choice = weave_internal.make_var_node(
            self.input_node.type.object_type, "choice"
        )
