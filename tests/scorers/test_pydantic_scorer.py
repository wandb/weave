import pytest
from pydantic import BaseModel

from weave.flow.scorer.pydantic_scorer import PydanticScorer


class User(BaseModel):
    name: str
    age: int

@pytest.fixture
def user_scorer():
    return PydanticScorer(model=User)

def test_pydantic_scorer_initialization():
    scorer = PydanticScorer(model=User)
    assert isinstance(scorer, PydanticScorer)
    assert scorer.model == User

def test_pydantic_scorer_valid_json_string(user_scorer):
    valid_json = '{"name": "John", "age": 30}'
    assert user_scorer.score(valid_json) == {"valid_pydantic": True}

def test_pydantic_scorer_valid_dict(user_scorer):
    valid_dict = {"name": "John", "age": 30}
    assert user_scorer.score(valid_dict) == {"valid_pydantic": True}

def test_pydantic_scorer_invalid_json_string(user_scorer):
    invalid_json = '{"name": "John", "age": "thirty"}'
    assert user_scorer.score(invalid_json) == {"valid_pydantic": False}

def test_pydantic_scorer_invalid_dict(user_scorer):
    invalid_dict = {"name": "John", "age": "thirty"}
    assert user_scorer.score(invalid_dict) == {"valid_pydantic": False}

def test_pydantic_scorer_missing_field(user_scorer):
    missing_field = '{"name": "John"}'
    assert user_scorer.score(missing_field) == {"valid_pydantic": False}

def test_pydantic_scorer_extra_field(user_scorer):
    extra_field = '{"name": "John", "age": 30, "city": "New York"}'
    assert user_scorer.score(extra_field) == {"valid_pydantic": True}

def test_pydantic_scorer_invalid_input_type(user_scorer):
    invalid_input = 123  # Neither a string nor a dict
    assert user_scorer.score(invalid_input) == {"valid_pydantic": False}