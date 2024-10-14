from weave.scorers import (
    LevenshteinScorer,
    StringMatchScorer,
)


def test_string_match_scorer():
    scorer = StringMatchScorer()
    output = "Morgan"
    target = "Hello my name is Morgan"
    result = scorer.score(output, target)
    assert result["string_in_input"] is True


def test_string_match_scorer_false():
    scorer = StringMatchScorer()
    output = "Alice"
    target = "Hello my name is Bob"
    result = scorer.score(output, target)
    assert result["string_in_input"] is False

def test_levenshtein_scorer():
    scorer = LevenshteinScorer()
    output = "Hello"
    target = "Hallo"
    result = scorer.score(output, target)
    assert result["levenshtein_distance"] == 1


def test_levenshtein_scorer_same_strings():
    scorer = LevenshteinScorer()
    output = "Hello"
    target = "Hello"
    result = scorer.score(output, target)
    assert result["levenshtein_distance"] == 0


def test_levenshtein_scorer_completely_different():
    scorer = LevenshteinScorer()
    output = "Hello"
    target = "World"
    result = scorer.score(output, target)
    assert result["levenshtein_distance"] == 4
