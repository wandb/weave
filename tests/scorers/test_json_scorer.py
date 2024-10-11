from weave.flow.scorer.json_scorer import JSONScorer

def test_json_scorer_valid_json():
    scorer = JSONScorer()
    output = '{"city": "San Francisco", "country": "USA"}'
    result = scorer.score(output)
    assert result["json_valid"] is True

def test_json_scorer_invalid_json():
    scorer = JSONScorer()
    output = '{"city": "San Francisco", "country": "USA"'
    result = scorer.score(output)
    assert result["json_valid"] is False

def test_json_scorer_non_json_string():
    scorer = JSONScorer()
    output = "Just a plain string."
    result = scorer.score(output)
    assert result["json_valid"] is False

def test_json_scorer_valid_json_list():
    scorer = JSONScorer()
    output = '[1, 2, 3, 4, 5]'
    result = scorer.score(output)
    assert result["json_valid"] is True

def test_json_scorer_nested_json():
    scorer = JSONScorer()
    output = '{"person": {"name": "John", "age": 30}, "city": "New York"}'
    result = scorer.score(output)
    assert result["json_valid"] is True

def test_json_scorer_empty_object():
    scorer = JSONScorer()
    output = '{}'
    result = scorer.score(output)
    assert result["json_valid"] is True

def test_json_scorer_empty_list():
    scorer = JSONScorer()
    output = '[]'
    result = scorer.score(output)
    assert result["json_valid"] is True
