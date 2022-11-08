import dataclasses
import copy
import typing
import weave

from .. import weave_internal
from .. import graph
from .. import panel
from .. import panel_util

ItemsType = typing.TypeVar("ItemsType")


@weave.type()
class Group2Config(typing.Generic[ItemsType]):
    layered: bool = dataclasses.field(default_factory=lambda: False)
    preferHorizontal: bool = dataclasses.field(default_factory=lambda: False)
    equalSize: bool = dataclasses.field(default_factory=lambda: False)
    style: str = dataclasses.field(default_factory=lambda: "")
    items: ItemsType = dataclasses.field(default_factory=dict)  # type: ignore


Group2ConfigType = typing.TypeVar("Group2ConfigType")


@weave.type()
class Group2(panel.Panel, typing.Generic[Group2ConfigType]):
    id = "Group2"
    config: typing.Optional[Group2ConfigType] = dataclasses.field(
        default_factory=lambda: None
    )
    # items: typing.TypeVar("items") = dataclasses.field(default_factory=dict)

    def __init__(self, input_node=graph.VoidNode(), vars=None, config=None, **options):
        if vars is None:
            vars = {}
        super().__init__(input_node=input_node, vars=vars)
        self.config = config
        if self.config is None:
            self.config = Group2Config()
        if "items" in options:
            self.config.items = options["items"]
        if "layered" in options:
            self.config.layered = options["layered"]
        if "preferHorizontal" in options:
            self.config.preferHorizontal = options["preferHorizontal"]
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

        for name, p in self.config.items.items():
            injected = panel.run_variable_lambdas(p, frame)
            child = panel_util.child_item(injected)
            if not isinstance(child, graph.Node):
                child._normalize(frame)
            self.config.items[name] = child

            # print("SELF CONFIG", self.config)
            config_var = weave_internal.make_var_node(
                weave.type_of(self.config), "self"
            )
            frame[name] = config_var.items[name]
            # print("FRAME", frame)
            # print()

    # @property
    # def config(self):
    #     self._normalize()
    #     return {"items": {k: i.to_json() for k, i in self.items.items()}}
