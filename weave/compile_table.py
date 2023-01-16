# Functions for optimizing table access sub-DAGs.

import typing

from . import errors
from . import stitch

KeyTree = typing.Dict[str, "KeyTree"]  # type:ignore


# Tree merges b into a IN PLACE
def tree_merge(a: KeyTree, b: KeyTree) -> None:
    for k, v in b.items():
        a_val = a.setdefault(k, {})
        if isinstance(v, dict):
            tree_merge(a_val, v)
        else:
            a_val[k] = v


def get_projection(obj: stitch.ObjectRecorder) -> KeyTree:
    """Given an object returned by stitch, return a tree of all accessed columns."""
    cols: KeyTree = {}
    for call in obj.calls_stitched_output_node_list:
        if call.node.from_op.name.endswith("pick") or call.node.from_op.name.endswith(
            "__getattr__"
        ):
            inputs = list(call.input_recorder_dict.values())
            if isinstance(inputs[1], stitch.ConstNodeObjectRecorder):
                key = inputs[1].const_value
                if key is not None:
                    tree_merge(
                        cols.setdefault(key, {}), get_projection(call.output_recorder)
                    )
                else:
                    raise errors.WeaveInternalError("null const not yet supported")
            else:
                raise errors.WeaveInternalError("non-const not yet supported")
        else:
            tree_merge(cols, get_projection(call.output_recorder))
    return cols
