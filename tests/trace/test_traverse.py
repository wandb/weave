import pytest

from weave.trace.traverse import ObjectPath, escape_key, get_paths, sort_paths


def test_escape_key() -> None:
    assert escape_key("") == ""
    assert escape_key("user") == "user"
    assert escape_key("user[name]") == "user\\[name\\]"
    assert escape_key("user.name[0]") == "user\\.name\\[0\\]"
    assert escape_key("user.name[0].name") == "user\\.name\\[0\\]\\.name"


class TestObjectPathToStr:
    def test_handles_empty_path(self) -> None:
        assert ObjectPath([]).to_str() == ""

    def test_handles_simple_cases(self) -> None:
        assert ObjectPath(["foo"]).to_str() == "foo"
        assert ObjectPath(["foo", "bar"]).to_str() == "foo.bar"
        assert ObjectPath(["foo", "4"]).to_str() == "foo.4"
        assert ObjectPath(["foo", 4]).to_str() == "foo[4]"

    def test_escapes_periods(self) -> None:
        assert ObjectPath(["foo.bar.baz"]).to_str() == "foo\\.bar\\.baz"

    def test_escapes_brackets(self) -> None:
        assert ObjectPath(["foo[5]"]).to_str() == "foo\\[5\\]"

    def test_str(self) -> None:
        assert str(ObjectPath(["foo", "bar"])) == "foo.bar"
        assert str(ObjectPath(["foo", 4])) == "foo[4]"


class TestObjectPathParseStr:
    def test_handles_empty_path(self) -> None:
        assert ObjectPath.parse_str("").elements == []

    def test_handles_simple_cases(self) -> None:
        assert ObjectPath.parse_str("foo").elements == ["foo"]
        assert ObjectPath.parse_str("foo.bar").elements == ["foo", "bar"]

    def test_handles_numeric_keys(self) -> None:
        assert ObjectPath.parse_str("0").elements == ["0"]
        assert ObjectPath.parse_str("42").elements == ["42"]

    def test_handles_punctuation_in_keys(self) -> None:
        assert ObjectPath.parse_str("a,b!").elements == ["a,b!"]

    def test_handles_key_access_errors(self) -> None:
        with pytest.raises(ValueError):
            ObjectPath.parse_str(".")
        with pytest.raises(ValueError):
            ObjectPath.parse_str("a[0].")
        with pytest.raises(ValueError):
            ObjectPath.parse_str("a..b")

    def test_handles_array_index_cases(self) -> None:
        assert ObjectPath.parse_str("foo[2]").elements == ["foo", 2]
        assert ObjectPath.parse_str("foo[2][3]").elements == ["foo", 2, 3]

    def test_handles_array_index_errors(self) -> None:
        with pytest.raises(ValueError):
            ObjectPath.parse_str("foo[")
        with pytest.raises(ValueError):
            ObjectPath.parse_str("foo[]")
        with pytest.raises(ValueError):
            ObjectPath.parse_str("foo[1e3]")
        with pytest.raises(ValueError):
            ObjectPath.parse_str("foo.[1]")

    def test_handles_escaped_chars(self) -> None:
        assert ObjectPath.parse_str("foo\\.bar").elements == ["foo.bar"]
        assert ObjectPath.parse_str("foo\\[").elements == ["foo["]

    def test_handles_escaping_errors(self) -> None:
        with pytest.raises(ValueError):
            ObjectPath.parse_str("foo\\")

    def test_handles_complex_cases(self) -> None:
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


class TestObjectPathDunderMethods:
    def test_hash(self) -> None:
        assert isinstance(hash(ObjectPath(["foo", 42, "bar"])), int)

    def test_getitem(self) -> None:
        path = ObjectPath(["foo", 42, "bar"])
        assert path[0] == "foo"
        assert path[1] == 42
        assert path[2] == "bar"

    def test_add(self) -> None:
        assert ObjectPath() + ["foo"] == ObjectPath(["foo"])
        assert ObjectPath(["foo"]) + [0] == ObjectPath(["foo", 0])
        assert ObjectPath(["foo"]) + [0, "bar"] == ObjectPath(["foo", 0, "bar"])

    def test_len(self) -> None:
        assert len(ObjectPath(["foo", 42, "bar"])) == 3

    def test_repr(self) -> None:
        assert repr(ObjectPath(["foo", 42, "bar"])) == "ObjectPath(['foo', 42, 'bar'])"


class TestObjectPathComparePaths:
    def test_simple_cases(self) -> None:
        assert ObjectPath(["foo"]).__eq__(42) is NotImplemented
        assert ObjectPath(["foo"]).__ne__(42) is NotImplemented
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


class TestObjectPathGetPaths:
    def test_object_cases(self) -> None:
        assert get_paths({}) == []
        assert get_paths({"foo": 42}) == [ObjectPath(["foo"])]
        assert get_paths({"foo": {"bar": 42}}) == [
            ObjectPath(["foo"]),
            ObjectPath(["foo", "bar"]),
        ]

    def test_list_cases(self) -> None:
        obj = {
            "foo": [
                {"bar": 42},
                {"baz": 43},
            ]
        }
        assert get_paths(obj) == [
            ObjectPath(["foo"]),
            ObjectPath(["foo", 0]),
            ObjectPath(["foo", 0, "bar"]),
            ObjectPath(["foo", 1]),
            ObjectPath(["foo", 1, "baz"]),
        ]


class TestObjectPathSortPaths:
    def test_sorting(self) -> None:
        assert sort_paths([]) == []
