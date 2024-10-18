from weave.scorers import ValidJSONScorer


def test_json_scorer_valid_json():
    scorer = ValidJSONScorer()
    output = '{"city": "San Francisco", "country": "USA"}'
    result = scorer.score(output)
    assert result["json_valid"] is True


def test_json_scorer_invalid_json():
    scorer = ValidJSONScorer()
    output = '{"city": "San Francisco", "country": "USA"'
    result = scorer.score(output)
    assert result["json_valid"] is False


def test_json_scorer_non_json_string():
    scorer = ValidJSONScorer()
    output = "Just a plain string."
    result = scorer.score(output)
    assert result["json_valid"] is False


def test_json_scorer_valid_json_list():
    scorer = ValidJSONScorer()
    output = "[1, 2, 3, 4, 5]"
    result = scorer.score(output)
    assert result["json_valid"] is True


def test_json_scorer_nested_json():
    scorer = ValidJSONScorer()
    output = '{"person": {"name": "John", "age": 30}, "city": "New York"}'
    result = scorer.score(output)
    assert result["json_valid"] is True


def test_json_scorer_empty_object():
    scorer = ValidJSONScorer()
    output = "{}"
    result = scorer.score(output)
    assert result["json_valid"] is True


def test_json_scorer_empty_list():
    scorer = ValidJSONScorer()
    output = "[]"
    result = scorer.score(output)
    assert result["json_valid"] is True
