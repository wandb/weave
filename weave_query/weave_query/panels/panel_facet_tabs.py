import dataclasses
import typing

import weave_query as weave

from weave_query.weave_query import graph, panel

RenderType = typing.TypeVar("RenderType")


@weave.type()
class FacetTabsConfig(typing.Generic[RenderType]):
    tab: weave.Node[typing.Optional[typing.Any]] = dataclasses.field(
        default_factory=lambda: weave_query.weave_query.graph.VoidNode()
    )
    panel: RenderType = dataclasses.field(default_factory=lambda: graph.VoidNode())  # type: ignore


@weave.type()
class FacetTabs(panel.Panel):
    id = "FacetTabs"
    config: typing.Optional[FacetTabsConfig] = dataclasses.field(
        default_factory=lambda: None
    )
