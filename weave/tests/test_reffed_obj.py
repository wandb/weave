import weave
from weave import storage
from weave import weave_types as types


def test_reffed_type():
    obj_ref = storage.save([1, 2, 3])
    obj = obj_ref.get()
    obj_type = types.type_of_with_refs(obj)
    assert obj_type == types.LocalArtifactRefType(types.List(types.Int()))


def test_save_reffed_obj():
    obj_ref = storage.save([1, 2, 3])
    obj = storage.get(str(obj_ref))
    obj_ref2 = storage.save(obj, "again")
    # Is this what we want or should it save?
    assert str(obj_ref) == str(obj_ref2)


def test_save_nested_reffed_obj():
    obj_ref = storage.save([1, 2, 3])
    obj = obj_ref.get()
    outer_obj = {"a": obj}
    outer_ref = storage.save(outer_obj)
    outer_obj2 = storage.get(str(outer_ref))
    obj2 = outer_obj2["a"]
    obj2_ref = storage.get_ref(obj2)
    assert str(obj_ref) == str(obj2_ref)


def test_save_awl_refs():
    obj1 = {"a": 5}
    obj1_ref = storage.save(obj1)
    obj2 = {"a": 6}
    obj2_ref = storage.save(obj2)
    wl = weave.WeaveList([obj1_ref, obj2_ref])
    wl_ref = storage.save(wl, "wl")
    wl2 = storage.get(str(wl_ref))

    assert wl2[0] == obj1
    assert str(weave.obj_ref(wl2[0])) == str(obj1_ref)
    assert wl2[1] == obj2
    assert str(weave.obj_ref(wl2[1])) == str(obj2_ref)
