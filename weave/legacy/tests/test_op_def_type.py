import typing

from weave.legacy.weave import op_def_type


class MyTypedDict(typing.TypedDict):
    a: int
    b: str
    c: typing.Union[int, str]


def test_generate_referenced_type_code():
    code = op_def_type.generate_referenced_type_code(list[MyTypedDict])
    assert (
        code
        == """class MyTypedDict(typing.TypedDict):
    a: int
    b: str
    c: typing.Union[int, str]
"""
    )
