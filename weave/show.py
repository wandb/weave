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
from . import errors
from . import usage_analytics
from .ops_primitives.weave_api import get as op_get


def is_json_compatible(obj):
    return isinstance(obj, (dict, list, str, int, float, bool))


def make_refs(node: graph.Node):
    # Wow this is a smell.
    # save_constant_vals = True
    # if isinstance(node, graph.OutputNode) and node.from_op.name == 'save':
    #     save_constant_vals = False
    def make_ref(node: graph.Node):
        if isinstance(node, graph.ConstNode):
            ref = storage.get_ref(node.val)
            if ref is not None:
                return op_get(str(ref.uri))
            # possibly wrong place - perhaps should be done in const node?, possibly need all branches from _show_params?, # will this match everything?
            # None when there is a 'get' op?!?!
            elif (
                node.val is not None
                and not is_json_compatible(node.val)
                and types.TypeRegistry.has_type(node.val)
            ):
                # print("Doing something special")
                obj = node.val
                from weave import ops

                names = util.find_names(obj)

                ref = storage.save(obj, name=names[-1])
                return weavejs_fixes.fixup_node(ops.get(ref.uri))
        return node

    return graph.map_nodes(node, make_ref)


# Broken out into to separate function for testing
def _show_params(obj):
    if obj is None:
        return {"weave_node": graph.VoidNode()}
    if isinstance(obj, graph.Node):
        return {"weave_node": weavejs_fixes.fixup_node(make_refs(obj))}

    elif isinstance(obj, panel.Panel):
        return {
            "weave_node": weavejs_fixes.fixup_node(obj.input_node),
            "panel_id": obj.id,
            "panel_config": weavejs_fixes.fixup_data(obj.config),
        }

    elif isinstance(obj, storage.Ref):
        from weave import ops

        node = ops.get(obj.uri)
        return {"weave_node": weavejs_fixes.fixup_node(node)}

    elif types.TypeRegistry.has_type(obj):
        from weave import ops

        names = util.find_names(obj)

        ref = storage.save(obj, name=names[-1])
        node = ops.get(ref.uri)

        return {"weave_node": weavejs_fixes.fixup_node(node)}

    else:
        raise errors.WeaveTypeError(
            "%s not yet supported. Create a weave.Type to add support." % type(obj)
        )


def show(obj=None, height=400):
    usage_analytics.show_called()

    if not util.is_notebook():
        raise RuntimeError(
            "`weave.show()` can only be called within notebooks. To extract the value of "
            "a weave node, try `weave.use()`."
        )

    params = _show_params(obj)
    panel_url = f"{context.get_frontend_url()}/__frontend/weave_jupyter?fullScreen"
    if "weave_node" in params:
        # print("JSON", params["weave_node"].to_json())
        panel_url += "&expNode=%s" % urllib.parse.quote(
            json.dumps(params["weave_node"].to_json())
        )
    if "panel_id" in params:
        panel_url += "&panelId=%s" % urllib.parse.quote(params["panel_id"])
    if "panel_config" in params:
        panel_url += "&panelConfig=%s" % urllib.parse.quote(
            json.dumps(params["panel_config"])
        )

    iframe = IFrame(panel_url, "100%", "%spx" % height)
    return display(iframe)
