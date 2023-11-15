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


def varbar(editable=True, items=None) -> panel_group.Group:
    showExpressions = True if editable else "titleBar"
    if items is None:
        items = {}
    return panel_group.Group(
        config=panel_group.GroupConfig(
            layoutMode="vertical",
            equalSize=False,
            style="width:300px;",
            showExpressions=showExpressions,  # type: ignore
            allowedPanels=[
                "Expression",
                "Query",
                "Slider",
                "StringEditor",
                "SelectEditor",
                "Dropdown",
                "DateRange",
                "FilterEditor",
                "GroupingEditor",
            ],
            enableAddPanel=editable,
            childNameBase="var",
        ),
        items=items,
    )


def Board(
    vars: typing.Union[panel_group.Group, list, dict],
    panels: typing.Union[panel_group.Group, list[BoardPanel]],
    editable=True,
):

    showExpressions = True if editable else "titleBar"
    vb = vars
    if not isinstance(vb, weave.panels.Group):
        vb = varbar(editable=editable, items=vars)

    main = panels
    if not isinstance(panels, weave.panels.Group):
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
            main = panel_group.Group(
                config=panel_group.GroupConfig(
                    layoutMode="grid",
                    showExpressions=showExpressions,  # type: ignore
                    enableAddPanel=True,
                    disableDeletePanel=True,
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
            )

    result = panel_group.Group(
        config=panel_group.GroupConfig(
            layoutMode="horizontal",
            showExpressions=False,
        ),
        items={"sidebar": vb, "main": main},
    )
    result.finalize()
    return result
