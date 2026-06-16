import pytest

from weave.trace.traverse import ObjectPath, escape_key, get_paths, sort_paths


def test_escape_key() -> None:
    assert escape_key("") == ""
    assert escape_key("user") == "user"
    assert escape_key("user[name]") == "user\\[name\\]"
    assert escape_key("user.name[0]") == "user\\.name\\[0\\]"
    assert escape_key("user.name[0].name") == "user\\.name\\[0\\]\\.name"


def test_object_path_to_str_and_str() -> None:
    """to_str renders dotted/indexed paths, escaping periods and brackets; str mirrors it."""
    assert ObjectPath([]).to_str() == ""
    assert ObjectPath(["foo"]).to_str() == "foo"
    assert ObjectPath(["foo", "bar"]).to_str() == "foo.bar"
    assert ObjectPath(["foo", "4"]).to_str() == "foo.4"
    assert ObjectPath(["foo", 4]).to_str() == "foo[4]"
    assert ObjectPath(["foo.bar.baz"]).to_str() == "foo\\.bar\\.baz"
    assert ObjectPath(["foo[5]"]).to_str() == "foo\\[5\\]"
    assert str(ObjectPath(["foo", "bar"])) == "foo.bar"
    assert str(ObjectPath(["foo", 4])) == "foo[4]"


def test_object_path_parse_str_valid() -> None:
    """parse_str handles empty, simple, numeric, punctuation, array-index, escapes, and complex paths."""
    assert ObjectPath.parse_str("").elements == []
    assert ObjectPath.parse_str("foo").elements == ["foo"]
    assert ObjectPath.parse_str("foo.bar").elements == ["foo", "bar"]
    assert ObjectPath.parse_str("0").elements == ["0"]
    assert ObjectPath.parse_str("42").elements == ["42"]
    assert ObjectPath.parse_str("a,b!").elements == ["a,b!"]
    assert ObjectPath.parse_str("foo[2]").elements == ["foo", 2]
    assert ObjectPath.parse_str("foo[2][3]").elements == ["foo", 2, 3]
    assert ObjectPath.parse_str("foo\\.bar").elements == ["foo.bar"]
    assert ObjectPath.parse_str("foo\\[").elements == ["foo["]
    assert ObjectPath.parse_str("fo\\.o[1].bar.baz.bim[3][5].wat").elements == [
        "fo.o",
        1,
        "bar",
        "baz",
        "bim",
        3,
        5,
        "wat",
    ]


@pytest.mark.parametrize(
    ("text", "match"),
    [
        (".", "Invalid object access"),
        ("a[0].", "Invalid object access"),
        ("a..b", "Invalid object access"),
        ("foo.[1]", "Invalid object access"),
        ("foo[", "Invalid array index"),
        ("foo[]", "Invalid array index"),
        ("foo[1e3]", "Invalid array index"),
        ("foo\\", "Invalid escape sequence"),
    ],
)
def test_object_path_parse_str_errors(text: str, match: str) -> None:
    with pytest.raises(ValueError, match=match):
        ObjectPath.parse_str(text)


def test_object_path_dunder_methods() -> None:
    """hash, getitem, add, len, and repr behave as expected."""
    path = ObjectPath(["foo", 42, "bar"])
    assert isinstance(hash(path), int)
    assert path[0] == "foo"
    assert path[1] == 42
    assert path[2] == "bar"
    assert len(path) == 3
    assert repr(path) == "ObjectPath(['foo', 42, 'bar'])"
    assert ObjectPath() + ["foo"] == ObjectPath(["foo"])
    assert ObjectPath(["foo"]) + [0] == ObjectPath(["foo", 0])
    assert ObjectPath(["foo"]) + [0, "bar"] == ObjectPath(["foo", 0, "bar"])


def test_object_path_comparisons() -> None:
    """Equality returns NotImplemented for foreign types; ordering compares element-wise."""
    assert ObjectPath(["foo"]).__eq__(42) is NotImplemented  # noqa: PLC2801
    assert ObjectPath(["foo"]).__ne__(42) is NotImplemented  # noqa: PLC2801
    assert ObjectPath(["foo"]) == ObjectPath(["foo"])
    assert ObjectPath(["foo"]) != ObjectPath(["foo", 42])
    assert ObjectPath(["foo", 10]) == ObjectPath(["foo", 10])
    assert ObjectPath(["foo"]) < ObjectPath(["foo", "bar"])
    assert ObjectPath(["foo"]) <= ObjectPath(["foo", "bar"])
    assert ObjectPath(["foo"]) <= ObjectPath(["foo"])
    assert ObjectPath(["foo", "bar"]) > ObjectPath(["foo"])
    assert ObjectPath(["foo", "bar"]) < ObjectPath(["foo", "baz"])
    assert ObjectPath(["foo", 9]) < ObjectPath(["foo", 10])
    assert ObjectPath(["foo", 11]) > ObjectPath(["foo", 1])
    assert ObjectPath(["foo", 11]) >= ObjectPath(["foo", 11])
    assert ObjectPath(["foo", "z"]) < ObjectPath(["foo", 0])
    assert not (ObjectPath(["foo", 0]) < ObjectPath(["foo", "a"]))


def test_get_paths_and_sort_paths() -> None:
    """get_paths walks objects and nested lists depth-first; sort_paths handles empty input."""
    assert get_paths({}) == []
    assert get_paths({"foo": 42}) == [ObjectPath(["foo"])]
    assert get_paths({"foo": {"bar": 42}}) == [
        ObjectPath(["foo"]),
        ObjectPath(["foo", "bar"]),
    ]
    list_obj = {"foo": [{"bar": 42}, {"baz": 43}]}
    assert get_paths(list_obj) == [
        ObjectPath(["foo"]),
        ObjectPath(["foo", 0]),
        ObjectPath(["foo", 0, "bar"]),
        ObjectPath(["foo", 1]),
        ObjectPath(["foo", 1, "baz"]),
    ]
    assert sort_paths([]) == []
