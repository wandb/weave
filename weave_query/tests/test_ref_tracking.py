import weave
from weave.legacy.weave import storage
from weave.legacy.weave import weave_types as types


def test_reffed_type(ref_tracking):
    obj_ref = storage.save([1, 2, 3])
    obj = obj_ref.get()
    obj_type = types.type_of_with_refs(obj)
    assert obj_type == types.LocalArtifactRefType(types.List(types.Int()))


def test_save_reffed_obj(ref_tracking):
    obj_ref = storage.save([1, 2, 3])
    obj = storage.get(str(obj_ref))
    obj_ref2 = storage.save(obj, "again")
    # Is this what we want or should it save?
    assert str(obj_ref) == str(obj_ref2)


def test_save_nested_reffed_obj(ref_tracking):
    obj_ref = storage.save([1, 2, 3])
    obj = obj_ref.get()
    outer_obj = {"a": obj}
    outer_ref = storage.save(outer_obj)
    outer_obj2 = storage.get(str(outer_ref))
    obj2 = outer_obj2["a"]
    obj2_ref = storage.get_ref(obj2)
    assert str(obj_ref) == str(obj2_ref)


def test_nested_object_deref(ref_tracking):
    @weave.type()
    class TestTypeA:
        val: int

    @weave.type()
    class TestTypeB:
        val: int
        a: TestTypeA

    a_ref = storage.save(TestTypeA(5))
    b_ref = storage.save(TestTypeB(6, a_ref))

    b = storage.get(str(b_ref))
    assert b.val == 6
    assert b.a.val == 5
