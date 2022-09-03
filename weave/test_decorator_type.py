import typing

import weave


def test_no_type_vars_in_dict():
    @weave.type()
    class TestNoTypeVarsInDictType:
        v: dict[str, int]

    assert not TestNoTypeVarsInDictType.WeaveType.type_vars()


def test_type_var_in_dict_any():
    @weave.type()
    class TestTypeVarsInDictType:
        v: dict[str, typing.Any]

    assert len(TestTypeVarsInDictType.WeaveType.type_vars()) == 1
