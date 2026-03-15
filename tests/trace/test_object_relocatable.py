import weave
from weave.trace.object_record import ObjectRecord
from weave.trace.refs import ObjectRef
from weave.trace.vals import WeaveObject


def test_object_ref_input_resolves(monkeypatch) -> None:
    class MyObj(weave.Object):
        val: int

    expected = MyObj(val=1)

    def fake_get(self, *, objectify: bool = True):  # type: ignore[no-untyped-def]
        return expected

    monkeypatch.setattr(ObjectRef, "get", fake_get)

    ref = ObjectRef(entity="ent", project="proj", name="MyObj", _digest="digest")
    result = MyObj.model_validate(ref)

    assert result is expected


def test_weaveobject_input_preserves_ref_and_ignored_types() -> None:
    class MyObj(weave.Object):
        value: int

    @weave.op
    def my_op() -> int:
        return 1

    ref = ObjectRef(entity="ent", project="proj", name="MyObj", _digest="digest")
    record = ObjectRecord(
        {
            "value": 3,
            "my_op": my_op,
            "_class_name": "MyObj",
            "_bases": [],
        }
    )
    weave_obj = WeaveObject(record, ref, None, None)

    result = MyObj.model_validate(weave_obj)

    assert result.value == 3
    assert result.ref == ref
    assert getattr(result, "my_op") is my_op
