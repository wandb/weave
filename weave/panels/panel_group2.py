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

    def normalize(self, _vars={}):
        vars = copy.copy(_vars)
        vars.update(self.vars)

        for name, p in self.items.items():
            injected = panel.inject_variables(p, vars)
            child = panel_util.child_item(injected)
            if not isinstance(child, graph.Node):
                child.normalize(vars)
            self.items[name] = child

            self_var = weave_internal.make_var_node(weave.type_of(self), "self")
            vars[name] = self_var.items[name]

        return vars

    def config(self, _vars={}):
        vars = self.normalize(_vars)
        final_items = {}
        for n, i in self.items.items():
            i = panel_util.child_item(i)
            if isinstance(i, graph.Node):
                final_items[n] = i.to_json()
            else:
                final_items[n] = i.to_json(vars)
        return {"items": final_items}
