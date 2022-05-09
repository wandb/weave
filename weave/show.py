import json
import urllib

from IPython.display import display
from IPython.display import IFrame

from . import context
from . import graph
from . import panel
from . import weave_types as types
from . import weavejs_fixes
from . import storage
from . import util
from . import usage_analytics
from .ops_primitives.storage import get as op_get


def make_refs(node: graph.Node):
    def make_ref(node: graph.Node):
        if isinstance(node, graph.ConstNode):
            ref = storage.get_ref(node.val)
            if ref is not None:
                return op_get(str(ref))
        return node

    return graph.map_nodes(node, make_ref)


# Broken out into to separate function for testing
def _show_params(obj):
    if isinstance(obj, graph.Node):
        return {"weave_node": weavejs_fixes.fixup_node(make_refs(obj))}
    elif isinstance(obj, storage.Ref):
        from weave import ops

        node = ops.get(str(obj))
        return {"weave_node": weavejs_fixes.fixup_node(node)}

    elif types.TypeRegistry.has_type(obj):
        from weave import ops

        names = util.find_names(obj)

        ref = storage.save(obj, name=names[-1])
        node = ops.get(str(ref))

        return {"weave_node": weavejs_fixes.fixup_node(node)}

    elif isinstance(obj, panel.Panel):
        return {
            "weave_node": weavejs_fixes.fixup_node(obj.input_node),
            "panel_id": obj.id,
            "panel_config": weavejs_fixes.fixup_data(obj.config),
        }

    else:
        raise Exception("pass a weave.Node or weave.Panel")


def show(obj):
    usage_analytics.show_called()

    if not util.is_notebook():
        raise RuntimeError(
            "`weave.show()` can only be called within notebooks. To extract the value of "
            "a weave node, try `weave.use()`."
        )

    params = _show_params(obj)
    panel_url = f"{context.get_frontend_url()}/index.html?fullScreen"
    if "weave_node" in params:
        panel_url += "&expNode=%s" % urllib.parse.quote(
            json.dumps(params["weave_node"].to_json())
        )
    if "panel_id" in params:
        panel_url += "&panelId=%s" % urllib.parse.quote(params["panel_id"])
    if "panel_config" in params:
        panel_url += "&panelConfig=%s" % urllib.parse.quote(
            json.dumps(params["panel_config"])
        )

    iframe = IFrame(panel_url, "100%", "300px")
    return display(iframe)
