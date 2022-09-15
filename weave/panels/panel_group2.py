import dataclasses
import copy
import typing
import weave

from .. import weave_internal
from .. import graph
from .. import panel
from .. import panel_util


@weave.type()
class Group2(panel.Panel):
    id = "group2"
    items: typing.TypeVar("items") = dataclasses.field(default_factory=dict)

    def _normalize(self, frame=None):
        if frame is None:
            frame = {}
        frame = copy.copy(frame)
        frame.update(self.vars)

        for name, p in self.items.items():
            injected = panel.run_variable_lambdas(p, frame)
            child = panel_util.child_item(injected)
            if not isinstance(child, graph.Node):
                child._normalize(frame)
            self.items[name] = child

            self_var = weave_internal.make_var_node(weave.type_of(self), "self")
            frame[name] = self_var.items[name]

    @property
    def config(self):
        self._normalize()
        return {"items": {k: i.to_json() for k, i in self.items.items()}}
