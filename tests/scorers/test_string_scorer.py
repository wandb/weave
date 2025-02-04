import pytest

from weave.scorers import (
    LevenshteinScorer,
    StringMatchScorer,
)


@pytest.mark.parametrize(
    "output, target, expected_result",
    [
        ("Morgan", "Hello my name is Morgan", True),
        ("Alice", "Hello my name is Bob", False),
    ],
)
def test_string_match_scorer(output, target, expected_result):
    scorer = StringMatchScorer()
    result = scorer.score(output, target)
    assert result.string_in_input is expected_result


@pytest.mark.parametrize(
    "output, target, expected_distance",
    [
        ("Hello", "Hallo", 1),
        ("Hello", "Hello", 0),
        ("Hello", "World", 4),
    ],
)
def test_levenshtein_scorer(output, target, expected_distance):
    scorer = LevenshteinScorer()
    result = scorer.score(output, target)
    assert result.levenshtein_distance == expected_distance
