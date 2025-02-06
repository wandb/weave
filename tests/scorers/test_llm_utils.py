from weave.scorers.utils import stringify


def test_stringify():
    assert stringify("Hello, world!") == "Hello, world!"
    assert stringify(123) == "123"
    assert stringify([1, 2, 3]) == "[\n  1,\n  2,\n  3\n]"
    assert stringify({"a": 1, "b": 2}) == '{\n  "a": 1,\n  "b": 2\n}'
