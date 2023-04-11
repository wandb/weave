import json
import random
import string
import urllib
import typing

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
from . import ref_base


def make_varname_for_type(t: types.Type):
    if isinstance(t, types.List) and isinstance(t.object_type, types.TypedDict):
        return "table"
    return t.name


def make_container(
    obj: typing.Union[panel.Panel, graph.Node], name: str
) -> panel.Panel:
    from weave.panels import Group

    return Group(preferHorizontal=True, showExpressions=True, items={name: obj})


def make_show_obj(obj: typing.Any):
    node: graph.Node
    if obj is None:
        return make_container(graph.VoidNode(), "panel0")
    elif isinstance(obj, panel.Panel):
        return make_container(obj, obj.id + "0")
    elif isinstance(obj, graph.Node):
        return make_container(obj, make_varname_for_type(obj.type) + "0")

    if types.TypeRegistry.has_type(obj):
        print("HAVE TYPE")
        from weave import ops

        names = util.find_names(obj)

        ref = storage.save(obj, name=names[-1])
        node = ops.get(ref.uri)
        return make_container(node, make_varname_for_type(ref.type))

    raise errors.WeaveTypeError(
        "%s not yet supported. Create a weave.Type to add support." % type(obj)
    )


# Broken out into to separate function for testing
def _show_params(obj):
    obj_in_container = make_show_obj(obj)
    ref = storage.save(obj_in_container, name="panel:latest")
    ref.artifact._version = "latest"
    show_node = graph.OutputNode(
        types.UnknownType(),
        "get",
        {"uri": graph.ConstNode(types.String(), str(ref))},
    )
    return {"weave_node": weavejs_fixes.fixup_node(show_node)}

    if obj is None:
        return {"weave_node": graph.VoidNode()}
    if isinstance(obj, graph.Node):
        if isinstance(obj, graph.OutputNode) and obj.from_op.name == "get":
            # If its a basic get op, remove the type from the node, the
            # frontend will fetch it by refining. We could do this for all nodes
            # since the frontend currently refines, but there may be compatibility bugs.
            # So for now just do it for get(), which will definitely refine correctly.
            # This allows us to send nodes of a fixed size (the length of a local artifact
            # uri plus a little overhead) via get parameter. We can store anything in artifacts,
            # so we can communicate any sized object to the browser this way.
            obj = graph.OutputNode(
                types.UnknownType(),
                "get",
                {"uri": obj.from_op.inputs["uri"]},
            )
        return {"weave_node": weavejs_fixes.fixup_node(obj)}

    elif isinstance(obj, panel.Panel):
        ref = storage.save(obj)
        node = graph.OutputNode(
            types.UnknownType(),
            "get",
            {"uri": graph.ConstNode(types.String(), str(ref))},
        )
        return {"weave_node": weavejs_fixes.fixup_node(node)}

        # converted = storage.to_python(obj)["_val"]

        # return {
        #     "weave_node": weavejs_fixes.fixup_node(obj.input_node),
        #     "panel_id": converted["id"],
        #     "panel_config": weavejs_fixes.fixup_data(converted["config"]),
        # }

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


def show_url(obj=None):
    params = _show_params(obj)
    panel_url = f"{context.get_frontend_url()}/__frontend/weave_jupyter?fullScreen"
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
    return panel_url


def show(obj=None, height=400):
    if not util.is_notebook():
        raise RuntimeError(
            "`weave.show()` can only be called within notebooks. To extract the value of "
            "a weave node, try `weave.use()`."
        )

    usage_analytics.show_called()
    panel_url = show_url(obj)

    iframe = IFrame(panel_url, "100%", "%spx" % height)
    display(iframe)


def _ipython_display_method_(self):
    show(self)


# Inject _ipython_display_ methods on classes we want to automatically
# show when the last expression in a notebook cell produces them.
graph.Node._ipython_display_ = _ipython_display_method_  # type: ignore
panel.Panel._ipython_display_ = _ipython_display_method_  # type: ignore
ref_base.Ref._ipython_display_ = _ipython_display_method_  # type: ignore
