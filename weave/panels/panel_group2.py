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
class PanelGroup2Config(typing.Generic[ItemsType]):
    items: ItemsType = dataclasses.field(default_factory=dict)


@weave.type()
class Group2(panel.Panel):
    id = "group2"
    config: PanelGroup2Config = None
    # items: typing.TypeVar("items") = dataclasses.field(default_factory=dict)

    def __init__(self, input_node=graph.VoidNode(), vars=None, **options):
        if vars is None:
            vars = {}
        super().__init__(input_node=input_node, vars=vars)
        self.config = PanelGroup2Config()
        if "items" in options:
            self.config.items = options["items"]
        self._normalize()

    def _normalize(self, frame=None):
        if frame is None:
            frame = {}
        frame = copy.copy(frame)
        frame.update(self.vars)

        for name, p in self.config.items.items():
            injected = panel.run_variable_lambdas(p, frame)
            print("INJECTED", injected)
            child = panel_util.child_item(injected)
            print("CHILD", child)
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
