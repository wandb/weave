import pytest

from weave.trace.object_record import ObjectRecord


def test_object_record_supports_subscript_for_str_format():
    """Regression: ObjectRecord must support __getitem__ so prompt templates
    using `{x[field]}` subscript syntax work. Without this, `str.format` on
    an ObjectRecord raised `TypeError: 'ObjectRecord' object is not
    subscriptable` — observed in weave-worker's
    scoring_worker._format_scoring_prompt.

    The `.format()` calls below are the behavior under test, so the UP032
    autofix to f-strings is suppressed.
    """
    rec = ObjectRecord({"_class_name": "Output", "answer": "42", "score": 0.9})

    # Direct subscript access mirrors attribute access.
    assert rec["answer"] == "42"
    assert rec["score"] == 0.9

    # Missing keys raise KeyError (dict semantics), not TypeError.
    with pytest.raises(KeyError, match="missing"):
        rec["missing"]

    # Production scenario: str.format with subscript syntax.
    assert "{out[answer]}".format(out=rec) == "42"  # noqa: UP032

    # Nested ObjectRecord subscripting recurses naturally.
    outer = ObjectRecord({"_class_name": "Outer", "inner": rec})
    assert "{x[inner][answer]}".format(x=outer) == "42"  # noqa: UP032
