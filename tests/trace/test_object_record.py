import pytest

from weave.trace.object_record import ObjectRecord


def test_object_record_getitem_returns_attribute():
    rec = ObjectRecord({"_class_name": "Foo", "x": 1, "y": "hi"})
    assert rec["x"] == 1
    assert rec["y"] == "hi"


def test_object_record_getitem_raises_keyerror_for_missing():
    rec = ObjectRecord({"_class_name": "Foo", "x": 1})
    with pytest.raises(KeyError, match="missing"):
        rec["missing"]


def test_object_record_str_format_with_subscript():
    """Regression: scoring prompts use `{var[field]}` subscript syntax.

    When a Weave call's input/output deserializes into an ObjectRecord, the
    private weave-worker's scoring prompt formatter calls
    `template.format(**inputs)`, which evaluates `inputs[var][field]` via
    `__getitem__`. Without this, format raised
    `TypeError: 'ObjectRecord' object is not subscriptable`.

    The `.format()` calls below are the behavior under test, so the UP032
    autofix to f-strings is suppressed.
    """
    rec = ObjectRecord({"_class_name": "Output", "answer": "42", "score": 0.9})
    assert "{out[answer]}".format(out=rec) == "42"  # noqa: UP032
    assert "score={out[score]}".format(out=rec) == "score=0.9"  # noqa: UP032


def test_object_record_str_format_nested():
    inner = ObjectRecord({"_class_name": "Inner", "name": "Alice"})
    outer = ObjectRecord({"_class_name": "Outer", "user": inner})
    assert "{x[user][name]}".format(x=outer) == "Alice"  # noqa: UP032
