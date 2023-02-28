from .. import weave_types as types
from .. import graph


# Reimplementation of Weave0 `toSafeCall` which
# converts media to their digest
def _to_compare_safe_call(node: graph.OutputNode) -> graph.OutputNode:
    from ..ops_primitives.dict import dict_
    from ..ops_domain.wbmedia import ArtifactAssetType

    node_type = types.non_none(node.type)
    if ArtifactAssetType.assign_type(node_type):
        # Must add this to all assets before merging
        return node.sha256  # type: ignore
    elif types.TypedDict({}).assign_type(node_type):
        new_keys = {}
        dirty = False
        for key in node_type.property_types.keys():  # type: ignore
            sub_key = node[key]  # type: ignore
            new_val = _to_compare_safe_call(sub_key)
            new_keys[key] = new_val
            if new_val is not sub_key:
                dirty = True
        if dirty:
            return dict_(**new_keys)
    elif types.List().assign_type(node_type):
        # AWL does not like joining on lists.
        return node.joinToStr(",")  # type: ignore
    return node
