import pytest

from weave.scorers import ValidJSONScorer


@pytest.mark.parametrize(
    "output, expected_result",
    [
        ('{"city": "San Francisco", "country": "USA"}', True),
        ('{"city": "San Francisco", "country": "USA"', False),
        ("Just a plain string.", False),
        ("[1, 2, 3, 4, 5]", True),
        ('{"person": {"name": "John", "age": 30}, "city": "New York"}', True),
        ("{}", True),
        ("[]", True),
    ],
)
def test_json_scorer(output, expected_result):
    scorer = ValidJSONScorer()
    result = scorer.score(output)
    assert result.json_valid == expected_result
