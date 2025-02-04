import pytest
from pydantic import BaseModel

from weave.scorers import PydanticScorer


class User(BaseModel):
    name: str
    age: int


@pytest.fixture
def user_scorer():
    return PydanticScorer(model=User)


@pytest.mark.parametrize(
    "input_data, expected_result",
    [
        ('{"name": "John", "age": 30}', {"valid_pydantic": True}),
        ({"name": "John", "age": 30}, {"valid_pydantic": True}),
        ('{"name": "John", "age": "thirty"}', {"valid_pydantic": False}),
        ({"name": "John", "age": "thirty"}, {"valid_pydantic": False}),
        ('{"name": "John"}', {"valid_pydantic": False}),
        ('{"name": "John", "age": 30, "city": "New York"}', {"valid_pydantic": True}),
        (123, {"valid_pydantic": False}),
    ],
)
def test_pydantic_scorer(user_scorer, input_data, expected_result):
    result = user_scorer.score(input_data)
    # Assert the result is a pydantic model with the attribute 'valid_pydantic'
    assert result.valid_pydantic == expected_result["valid_pydantic"]
