import pytest

from weave.utils.invertable_dict import InvertableDict

pytestmark = pytest.mark.trace_server


def test_invertable_dict_construction_and_access():
    mapping = InvertableDict({"jpg": "jpeg", "png": "png"})

    # Default mapping -- looks and acts like a regular dict
    assert len(mapping) == 2
    assert mapping["jpg"] == "jpeg"
    assert mapping["png"] == "png"
    assert sorted(iter(mapping)) == ["jpg", "png"]

    # Inverse mapping -- looks and acts like a regular dict
    assert len(mapping.inv) == 2
    assert mapping.inv["jpeg"] == "jpg"
    assert mapping.inv["png"] == "png"
    assert sorted(iter(mapping.inv)) == ["jpeg", "png"]


def test_invertable_dict_rejects_duplicate_values_on_init():
    with pytest.raises(ValueError, match="Duplicate value found: jpeg"):
        InvertableDict({"jpg": "jpeg", "jpe": "jpeg"})


def test_invertable_dict_inverse_roundtrip():
    mapping = InvertableDict({"a": 1, "b": 2})

    assert mapping.inv[1] == "a"
    assert mapping.inv[2] == "b"
    assert mapping.inv.inv["a"] == 1
    assert mapping.inv.inv["b"] == 2


def test_invertable_dict_mutation_updates_inverse_view():
    mapping = InvertableDict({"a": 1})
    inverse = mapping.inv

    mapping["b"] = 2
    mapping["a"] = 3

    assert inverse[2] == "b"
    assert inverse[3] == "a"
    assert 1 not in inverse


def test_invertable_dict_inverse_mutation_updates_forward_view():
    mapping = InvertableDict({"a": 1})
    inverse = mapping.inv

    inverse[2] = "b"

    assert mapping["b"] == 2
    assert inverse[2] == "b"


def test_invertable_dict_delete_updates_inverse_view():
    mapping = InvertableDict({"a": 1, "b": 2})
    inverse = mapping.inv

    del mapping["a"]

    assert "a" not in mapping
    assert 1 not in inverse
    assert inverse[2] == "b"


def test_invertable_dict_rejects_duplicate_values_on_set():
    mapping = InvertableDict({"a": 1})

    with pytest.raises(ValueError, match="Duplicate value found: 1"):
        mapping["b"] = 1
