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
    for call in obj.calls:
        if call.op_name.endswith("pick") or call.op_name.endswith("__getattr__"):
            key = call.inputs[1].val
            if key is None:
                raise errors.WeaveInternalError("non-const not yet supported")
            tree_merge(cols.setdefault(key, {}), get_projection(call.output))
        else:
            tree_merge(cols, get_projection(call.output))
    return cols
