import dataclasses
import typing

import weave
from .. import panel
from .. import panel_util
from .. import graph

CardContentType = typing.TypeVar("CardContentType")


@weave.type()
class CardTab(typing.Generic[CardContentType]):
    name: str
    content: CardContentType


@weave.type()
class CardConfig:
    title: weave.Node[str]
    subtitle: str
    content: list[CardTab]


@weave.type()
class Card(panel.Panel):
    id = "Card"
    config: typing.Optional[CardConfig] = dataclasses.field(
        default_factory=lambda: None
    )

    def __init__(self, input_node=graph.VoidNode(), vars=None, config=None, **options):
        super().__init__(input_node=input_node, vars=vars)
        self.config = config
        if self.config is None:
            self.config = CardConfig(
                panel_util.make_node(options["title"]),
                options["subtitle"],
                options["content"],
            )
