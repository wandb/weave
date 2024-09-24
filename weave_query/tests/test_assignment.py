import pytest

import weave

types = weave.types.get_type_classes()


@pytest.mark.parametrize("type_name, type_cls", [(t.name, t) for t in types])
def test_const_assignment(type_name, type_cls):
    from weave.legacy.weave.ops_domain import wb_domain_types as wdt

    params = []
    # Quick list of types that don't work with this parametrization
    if type_name in ["const", "invalid", "union", "function", "unknown"]:
        return

    # Special types that need extra params
    if type_name == "list":
        params = [weave.types.String()]
    if type_name == "typedDict":
        params = [{"col": weave.types.String()}]
    if type_name == "dict":
        params = [weave.types.String(), weave.types.String()]
    if type_name == "dataframe":
        params = [weave.types.TypedDict({"col": weave.types.String()})]
    if type_name == "tagged":
        params = [
            weave.types.TypedDict({"col": weave.types.String()}),
            weave.types.String(),
        ]
    if type_name == "PartialObject":
        params = [
            type(wdt.RunType),
            weave.types.TypedDict({"col": weave.types.String()}),
        ]

    cls_type = type_cls(*params)
    const_type = weave.types.Const(
        cls_type, None
    )  # technically `None` is invalid, but we're just testing the assignment

    # Validate that you can assign a const type to a general type
    assert cls_type.assign_type(const_type)

    # strict Const assignability is disabled. See weave_types.py and
    # test_plot_constants_assign
    # Validate that you cannot assign a general type to a const type
    # assert not const_type.assign_type(cls_type)

    # Validate that unions are automatically unwrapped
    union_type = weave.types.UnionType(cls_type, const_type)
    assert union_type.assign_type(const_type)
    assert union_type.assign_type(cls_type)
    assert cls_type.assign_type(union_type)

    # strict Const assignability is disabled. See weave_types.py and
    # test_plot_constants_assign
    # assert not const_type.assign_type(union_type)
