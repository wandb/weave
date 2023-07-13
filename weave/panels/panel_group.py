import dataclasses
import copy
import typing
import weave
from weave import codifiable_value_mixin
from weave import codify

from .. import weave_internal
from .. import graph
from .. import panel
from .. import panel_util
from .bank import default_panel_bank_flow_section_config, flow_layout

from .panel_group_panel_info import PanelInfo

ItemsType = typing.TypeVar("ItemsType")

# I pulled in all the type information from PanelBank, but we're not
# using it all yet.


class LayoutParameters(typing.TypedDict):
    x: int
    y: int
    w: int
    h: int


class LayedOutPanel(typing.TypedDict):
    id: str
    layout: LayoutParameters


class PanelBankFlowSectionConfig(typing.TypedDict):
    snapToColumns: bool
    columnsPerPage: int
    rowsPerPage: int
    gutterWidth: int
    boxWidth: int
    boxHeight: int


class PanelBankSectionConfig(typing.TypedDict):
    id: str
    name: str
    panels: typing.List[LayedOutPanel]
    isOpen: bool
    flowConfig: PanelBankFlowSectionConfig
    type: str  # this 'grid' | 'flow' in ts
    sorted: int  # This is an enum in js


@weave.type()
class GroupConfig(typing.Generic[ItemsType]):
    layoutMode: str = dataclasses.field(default_factory=lambda: "vertical")
    showExpressions: typing.Union[bool, typing.Literal["editable"]] = dataclasses.field(
        default_factory=lambda: False
    )
    equalSize: bool = dataclasses.field(default_factory=lambda: False)
    style: str = dataclasses.field(default_factory=lambda: "")
    items: ItemsType = dataclasses.field(default_factory=dict)  # type: ignore
    panelInfo: typing.Optional[dict[str, typing.Any]] = dataclasses.field(
        default_factory=lambda: None
    )
    gridConfig: typing.Optional[PanelBankSectionConfig] = dataclasses.field(
        default_factory=lambda: None
    )
    liftChildVars: typing.Optional[bool] = dataclasses.field(
        default_factory=lambda: None
    )
    allowedPanels: typing.Optional[list[str]] = dataclasses.field(
        default_factory=lambda: None
    )
    enableAddPanel: typing.Optional[bool] = dataclasses.field(
        default_factory=lambda: None
    )
    childNameBase: typing.Optional[str] = dataclasses.field(
        default_factory=lambda: None
    )


GroupConfigType = typing.TypeVar("GroupConfigType")


@dataclasses.dataclass
class GroupLayoutFlow:
    rows: int
    columns: int


@dataclasses.dataclass
class GroupPanelLayout:
    x: int
    y: int
    h: int
    w: int


@dataclasses.dataclass
class GroupPanel:
    panel: typing.Any
    id: typing.Optional[str] = None
    hidden: typing.Optional[bool] = None
    # Only used inside a grid layout
    layout: typing.Optional[GroupPanelLayout] = None


@weave.type()
class Group(panel.Panel, codifiable_value_mixin.CodifiableValueMixin):
    id = "Group"
    config: typing.Optional[GroupConfig] = dataclasses.field(
        default_factory=lambda: None
    )
    # items: typing.TypeVar("items") = dataclasses.field(default_factory=dict)

    def __init__(
        self, input_node=graph.VoidNode(), vars=None, config=None, **options
    ) -> None:
        super().__init__(input_node=input_node, vars=vars)
        self.config = config
        if self.config is None:
            self.config = GroupConfig()
        if "layoutMode" in options:
            layout_mode = options["layoutMode"]
            if isinstance(layout_mode, GroupLayoutFlow):
                self.config.layoutMode = "flow"
                self.config.gridConfig = flow_layout(
                    layout_mode.rows, layout_mode.columns
                )
            else:
                self.config.layoutMode = layout_mode
                self.config.gridConfig = default_panel_bank_flow_section_config()
        if "items" in options:
            if isinstance(options["items"], dict):
                self.config.items = options["items"]
            else:
                options_dict = {}
                panel_info = {}
                for o in options["items"]:
                    if isinstance(o, GroupPanel):
                        options_dict[o.id] = o.panel
                        panel_info[o.id] = {"hidden": o.hidden}
                    else:
                        raise ValueError("Items must be GroupPanel")
                self.config.items = options_dict
                if panel_info:
                    self.config.panelInfo = panel_info  # type: ignore

        if "showExpressions" in options:
            self.config.showExpressions = options["showExpressions"]
        if "enableAddPanel" in options:
            self.config.enableAddPanel = options["enableAddPanel"]
        if "equalSize" in options:
            self.config.equalSize = options["equalSize"]
        if "style" in options:
            self.config.style = options["style"]
        self._normalize()

    def _normalize(self, frame=None):
        if frame is None:
            frame = {}
        frame = copy.copy(frame)
        frame.update(self.vars)
        frame["input"] = self.input_node

        items = {}
        for name, p in self.config.items.items():
            try:
                injected = panel.run_variable_lambdas(p, frame)
            except weave.errors.WeaveDefinitionError:
                return
            child = panel_util.child_item(injected)
            if not isinstance(child, graph.Node):
                child._normalize(frame)
            if isinstance(child, Group):
                # lift group vars
                for child_name, child_item in child.config.items.items():
                    frame[child_name] = weave_internal.make_var_node(
                        weave.type_of(child_item), child_name
                    )
            items[name] = child

            # We build up config one item at a time. Construct a version
            # with the current items so that we can do type_of on it (type_of
            # will fail if we have a lambda in the config).
            partial_config = dataclasses.replace(self.config, items=items)
            config_var = weave_internal.make_var_node(
                weave.type_of(partial_config), "self"
            )
            frame[name] = config_var.items[name]

        self.config.items = items

    def to_code(self) -> typing.Optional[str]:
        field_vals: list[tuple[str, str]] = []

        if self.config and self.config:
            gc = self.config

            if gc.equalSize != False:
                return None
            if gc.style != "":
                return None
            if (
                gc.gridConfig is not None
                and gc.gridConfig != default_panel_bank_flow_section_config()
            ):
                return None
            if gc.liftChildVars is not None:
                return None
            if gc.allowedPanels is not None:
                return None
            if gc.childNameBase is not None:
                return None

            if self.config.layoutMode != "vertical":
                field_vals.append(("layoutMode", codify.object_to_code(gc.layoutMode)))
            if gc.showExpressions != False:
                field_vals.append(
                    ("showExpressions", codify.object_to_code(gc.showExpressions))
                )
            if hasattr(gc, "layered") and gc.layered != False:
                field_vals.append(("layered", codify.object_to_code(gc.layered)))
            if gc.enableAddPanel != None and gc.enableAddPanel != False:
                field_vals.append(
                    ("enableAddPanel", codify.object_to_code(gc.enableAddPanel))
                )
            prior_vars: list[str] = []
            code_items_map = {}
            if gc.items != {}:
                for item_name, item in gc.items.items():
                    code_items_map[
                        item_name
                    ] = codify.lambda_wrapped_object_to_code_no_format(item, prior_vars)
                    prior_vars.append(item_name)
                if len(code_items_map) > 0:
                    items_val = (
                        ",".join(
                            ['"' + n + '":' + i for n, i in code_items_map.items()]
                        )
                        + ","
                    )
                    items_val = "{" + items_val + "}"
                    field_vals.append(("items", items_val))

        input_node_str = ""
        if not isinstance(self.input_node, graph.VoidNode):
            input_node_str = codify.object_to_code(self.input_node) + ","

        param_str = ""
        if len(field_vals) > 0:
            param_str = (
                ",".join([f_name + "=" + f_val for f_name, f_val in field_vals]) + ","
            )
        return f"""weave.panels.panel_group.Group({input_node_str} {param_str})"""

    # @property
    # def config(self):
    #     self._normalize()
    #     return {"items": {k: i.to_json() for k, i in self.items.items()}}
