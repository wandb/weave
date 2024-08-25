import pytest

from weave.legacy.weave.ops_primitives.string import _levenshtein


@pytest.mark.parametrize(
    "str1,str2,expected",
    [
        ["", "", 0],
        ["a", "a", 0],
        ["", "a", 1],
        ["a", "b", 1],
        ["a", "ab", 1],
        ["ab", "ac", 1],
        ["ab", "ba", 2],
        ["", "ab", 2],
        ["ab", "cd", 2],
        ["abc", "cab", 2],
        ["", "abc", 3],
        ["abc", "def", 3],
    ],
)
def test_levenshtein(str1, str2, expected):
    assert _levenshtein(str1, str2) == expected
    assert _levenshtein(str2, str1) == expected
