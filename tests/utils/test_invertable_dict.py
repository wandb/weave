import pytest

from weave.utils.invertable_dict import InvertableDict

pytestmark = pytest.mark.trace_server


def test_invertable_dict_access_and_inverse_roundtrip():
    mapping = InvertableDict({"jpg": "jpeg", "png": "png"})

    # Forward mapping acts like a regular dict.
    assert len(mapping) == 2
    assert mapping["jpg"] == "jpeg"
    assert mapping["png"] == "png"
    assert sorted(iter(mapping)) == ["jpg", "png"]

    # Inverse mapping acts like a regular dict.
    assert len(mapping.inv) == 2
    assert mapping.inv["jpeg"] == "jpg"
    assert mapping.inv["png"] == "png"
    assert sorted(iter(mapping.inv)) == ["jpeg", "png"]

    # Double-inverse returns to the forward view.
    nums = InvertableDict({"a": 1, "b": 2})
    assert nums.inv[1] == "a"
    assert nums.inv[2] == "b"
    assert nums.inv.inv["a"] == 1
    assert nums.inv.inv["b"] == 2


def test_invertable_dict_mutations_keep_views_in_sync():
    mapping = InvertableDict({"a": 1, "b": 2})
    inverse = mapping.inv

    # Forward set adds and reassigns, dropping the stale inverse key.
    mapping["c"] = 3
    mapping["a"] = 4
    assert inverse[3] == "c"
    assert inverse[4] == "a"
    assert 1 not in inverse

    # Inverse set writes through to the forward view.
    inverse[5] = "d"
    assert mapping["d"] == 5
    assert inverse[5] == "d"

    # Forward delete removes both directions.
    del mapping["b"]
    assert "b" not in mapping
    assert 2 not in inverse


@pytest.mark.parametrize(
    ("build", "match"),
    [
        (
            lambda: InvertableDict({"jpg": "jpeg", "jpe": "jpeg"}),
            "Duplicate value found: jpeg",
        ),
        (lambda: _set_duplicate(), "Duplicate value found: 1"),
    ],
    ids=["on-init", "on-set"],
)
def test_invertable_dict_rejects_duplicate_values(build, match):
    with pytest.raises(ValueError, match=match):
        build()


def _set_duplicate() -> None:
    mapping = InvertableDict({"a": 1})
    mapping["b"] = 1
