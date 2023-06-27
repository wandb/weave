# TODO: move all panelbank stuff here

from . import panel_group


def default_panel_bank_flow_section_config():
    return panel_group.PanelBankSectionConfig(
        id="grid0",
        name="Section 0",
        panels=[],
        isOpen=True,
        flowConfig=panel_group.PanelBankFlowSectionConfig(
            snapToColumns=True,
            columnsPerPage=1,
            rowsPerPage=1,
            gutterWidth=0,
            boxWidth=64,
            boxHeight=64,
        ),
        type="grid",
        sorted=0,
    )


# TODO: temporary state, need a better way to declare this.
def flow_nxn(rows: int, columns: int):
    conf = default_panel_bank_flow_section_config()
    conf["flowConfig"]["columnsPerPage"] = columns
    conf["flowConfig"]["rowsPerPage"] = rows
    return conf
