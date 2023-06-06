import dataclasses
import typing

import weave
from .. import panel
from .. import weave_internal

from . import panel_group


# @dataclasses.dataclass
# class Board:
#     vars: typing.Dict[str, typing.Any]
#     panels: typing.Dict[str, typing.Any]


@dataclasses.dataclass
class BoardPanelLayout:
    x: int
    y: int
    h: int
    w: int


@dataclasses.dataclass
class BoardPanel:
    panel: typing.Any
    id: typing.Optional[str] = None
    layout: typing.Optional[BoardPanelLayout] = None


def Board(vars, panels: list[BoardPanel]):
    main_items = {}
    main_panel_layouts: list[panel_group.LayedOutPanel] = []
    for i, p in enumerate(panels):
        id = p.id
        if id is None:
            id = "panel" + str(i)
        main_items[id] = p.panel
        if p.layout is not None:
            main_panel_layouts.append(
                panel_group.LayedOutPanel(
                    id=id,
                    layout=panel_group.LayoutParameters(
                        x=p.layout.x,
                        y=p.layout.y,
                        w=p.layout.w,
                        h=p.layout.h,
                    ),
                )
            )
    return panel_group.Group(
        config=panel_group.GroupConfig(
            layoutMode="horizontal",
            showExpressions=False,
        ),
        items={
            "sidebar": panel_group.Group(
                config=panel_group.GroupConfig(
                    layoutMode="vertical",
                    equalSize=False,
                    style="width:300px;",
                    showExpressions=True,
                    allowedPanels=["Expression", "Query", "Slider", "StringEditor"],
                    enableAddPanel=True,
                    childNameBase="var",
                ),
                items=vars,
            ),
            "main": panel_group.Group(
                config=panel_group.GroupConfig(
                    layoutMode="grid",
                    showExpressions=True,
                    enableAddPanel=True,
                    gridConfig=panel_group.PanelBankSectionConfig(
                        id="grid0",
                        name="Section 0",
                        panels=main_panel_layouts,
                        isOpen=True,
                        flowConfig=panel_group.PanelBankFlowSectionConfig(
                            snapToColumns=True,
                            columnsPerPage=3,
                            rowsPerPage=2,
                            gutterWidth=10,
                            boxWidth=256,
                            boxHeight=256,
                        ),
                        type="grid",
                        sorted=0,
                    ),
                ),
                items=main_items,
            ),
        },
    )
