from pydantic import BaseModel, Field

from weave.trace.object_record import pydantic_asdict_one_level


class MyClass(BaseModel):
    name: str
    age: int = Field(alias="age_alias")
    secret: str = Field(exclude=True)


def test_pydantic_asdict_one_level():
    my_class = MyClass(name="John", age=30, secret="secret")
    assert pydantic_asdict_one_level(my_class) == {
        "name": "John",
        "age_alias": 30,
    }
