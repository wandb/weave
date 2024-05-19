import typing

import weave


def test_type_var_in_dict_any():
    @weave.type()
    class TestTypeVarsInDictType:
        v: dict[str, typing.Any]

    assert len(TestTypeVarsInDictType.WeaveType.type_attrs()) == 1


def test_object_union_attr_is_variable():
    @weave.type()
    class ObjWithUnion:
        a: typing.Union[str, int]

    assert "a" in ObjWithUnion.WeaveType().type_vars


def test_object_noneunion_attr_is_variable():
    @weave.type()
    class ObjWithUnion:
        a: weave.Node[typing.Union[str, int]]

    assert "a" in ObjWithUnion.WeaveType().type_vars


def test_type_is_reloctable():
    @weave.type()
    class CoolObjBase:
        pass

    @weave.type()
    class CoolObj(CoolObjBase):
        a: int
        b: str

    obj = CoolObj(1, "hi")
    ref = weave.storage.save(obj)
    obj2 = weave.storage.get(str(ref))
    assert obj2.a == 1


def test_type_with_name():
    @weave.type()
    class CoolObjWithName:
        name: str
        a: int

    obj = CoolObjWithName("my-name", 15)
    ref = weave.storage.save(obj)
    obj2 = weave.storage.get(str(ref))
    assert obj2.a == 15
    assert obj2.name == "my-name"
