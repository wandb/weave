from ..decorators import op
from .. import weave_types as types


def get_const_union_vals(type_, of_type):
    if isinstance(type_, types.Const):
        if type_.val_type != of_type:
            return None
        return [type_.val]
    if not isinstance(type_, types.UnionType):
        return None
    vals = []
    for m in type_.members:
        if not isinstance(m, types.Const) or not m.val_type == of_type:
            return None
        vals.append(m.val)
    return vals


def union_output_type(input_type):
    s1_type = input_type["s1"].object_type
    s2_type = input_type["s2"].object_type
    vals1 = get_const_union_vals(s1_type, types.String())
    vals2 = get_const_union_vals(s2_type, types.String())
    if vals1 and vals2:
        union_vals = set(vals1).union(vals2)
        return types.List(
            types.UnionType(*(types.Const(types.String(), v) for v in union_vals))
        )
    return types.List(types.String())


# TODO: generic
@op(output_type=union_output_type)
def union(s1: list[str], s2: list[str]):
    return list(set(s1).union(set(s2)))


def difference_output_type(input_type):
    s1_type = input_type["s1"].object_type
    s2_type = input_type["s2"].object_type
    vals1 = get_const_union_vals(s1_type, types.String())
    vals2 = get_const_union_vals(s2_type, types.String())
    if vals1 and vals2:
        union_vals = set(vals1).difference(vals2)
        return types.List(
            types.union(*(types.Const(types.String(), v) for v in union_vals))
        )
    return types.List(types.String())


@op(output_type=difference_output_type)
def difference(s1: list[str], s2: list[str]):
    return list(set(s1).difference(set(s2)))
