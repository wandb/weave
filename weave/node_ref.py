import typing
import copy

from . import graph
from . import ref_base
from . import ops

# Notes for the future:
# - I added list.lookup to lookup rows in a list by ID. I think we probably should
# add a weave.Table type which is a list of dicts that have ID. Then we can define
# node reference to use id lookup instead of index. Maybe figure out how to make
# it a multi-index so we can match pandas.


def node_to_ref(node: graph.Node) -> typing.Optional[ref_base.Ref]:
    """Converts a Node to equivalent Ref if possible.

    Specific call sequences can be converted to refs. For example:
      get(<object_path>)[0]['a'] can be converted to a Ref.

    The rule is:
      - a get call can be converted to a Ref
      - any __getitem__ (or pick) call can be converted to a Ref if its input is a Node
        that can be converted to a Ref

    It's desirable to store these as Refs rather than nodes because:
      - The representation is much more compact
      - A ref is a guarantee of existence
      - Artifacts is aware of cross-artifact references and keeps them
        consistent (it does not allow deleting an artifact that has existing
          depending artifacts)

    This is used when saving objects, to achieve cross-artifact references.

    A user may compose objects from values fetched from other objects. For example:
    x = weave.save({'a': 5})
    y = weave.save({'b': x['a']})

    Since Weave is lazy, x['a'] produces a Node. When we save objects, if a Node
      is encountered we try to convert it to a Ref using this function. If that
      succeeds, we save in Ref format instead of Node format.

    # TODO: we need to tell the artifact this Ref exists, so that it creates
    #   the database dependency, which is how we achieve consistency.
    """
    nodes = graph.linearize(node)
    if nodes is None:
        return None

    # First node in chain must be get op
    # TODO: check it's a get of a specific artifact version, not an alias!
    #     maybe we should have two different ops for that, so we can distinguish
    #     via type instead of via string checking.
    if nodes[0].from_op.name != "get":
        return None
    get_arg0 = list(nodes[0].from_op.inputs.values())[0]
    if not isinstance(get_arg0, graph.ConstNode):
        return None
    uri = get_arg0.val
    ref = ref_base.Ref.from_str(uri)
    if ref.extra is None:
        ref.extra = []

    # Remaining nodes in chain must be __getitem__
    for node in nodes[1:]:
        if not (
            node.from_op.name.endswith("__getitem__")
            # Allow pick too, but this is kinda busted. What if both exist?
            # I think we should maybe just use __getitem__ to implement both
            # of these. If passed a string, it's a column lookup, int is row
            # lookup. Some other tools do this. However, if that's the solution,
            # then our "ref extra is list of string" solution doesn't work.
            # TODO: fix
            or node.from_op.name.endswith("pick")
            or node.from_op.name.endswith("index")
        ):
            return None
        getitem_arg1 = list(node.from_op.inputs.values())[1]
        if not isinstance(getitem_arg1, graph.ConstNode):
            return None
        ref.extra.append(str(getitem_arg1.val))
    return ref


def ref_to_node(ref: ref_base.Ref) -> typing.Optional[graph.Node]:
    """Inverse of node_to_ref, see docstring for node_to_ref."""

    extra = ref.extra or []
    ref = copy.copy(ref)
    ref.extra = []

    node = ops.get(str(ref))
    for str_key in extra:
        key: typing.Union[str, int] = str_key
        try:
            key = int(str_key)
        except ValueError:
            pass
        if hasattr(node, "__getitem__"):
            node = node[key]  # type: ignore
        elif hasattr(node, "pick"):
            node = node.pick(key)  # type: ignore
        else:
            return None
    return node
