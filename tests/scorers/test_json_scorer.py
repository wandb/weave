import pytest

from weave.scorers import ValidJSONScorer


@pytest.mark.parametrize(
    ("output", "expected_result"),
    [
        ('{"city": "San Francisco", "country": "USA"}', True),
        ('{"city": "San Francisco", "country": "USA"', False),
        ("Just a plain string.", False),
        ("[1, 2, 3, 4, 5]", True),
        ('{"person": {"name": "John", "age": 30}, "city": "New York"}', True),
        ("{}", True),
        ("[]", True),
        # Non-string outputs must score False, not raise TypeError.
        # A timed-out model, a content filter, or a structured-output adapter
        # can all produce None or a non-string value.
        (None, False),
        ({}, False),
        ([], False),
        (42, False),
    ],
)
def test_json_scorer(output, expected_result):
    scorer = ValidJSONScorer()
    result = scorer.score(output=output)
    assert result["json_valid"] is expected_result
