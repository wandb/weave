import pytest

import weave
from tests.trace.person_pb2 import Person


def test_protobuf_input(client):
    @weave.op()
    def process_person(person: Person) -> str:
        return f"Name: {person.name}, Age: {person.age}, Email: {person.email}"

    person = Person(name="Alice", age=30, email="alice@example.com")
    result = process_person(person)
    assert result == "Name: Alice, Age: 30, Email: alice@example.com"

    calls = list(client.get_calls())
    assert len(calls) == 1
    assert calls[0].inputs["person"].name == "Alice"
    assert calls[0].inputs["person"].age == 30
    assert calls[0].inputs["person"].email == "alice@example.com"
    assert calls[0].output == "Name: Alice, Age: 30, Email: alice@example.com"


def test_protobuf_output(client):
    @weave.op()
    def create_person(name: str, age: int, email: str) -> Person:
        return Person(name=name, age=age, email=email)

    result = create_person("Bob", 25, "bob@example.com")
    assert isinstance(result, Person)
    assert result.name == "Bob"
    assert result.age == 25
    assert result.email == "bob@example.com"

    calls = list(client.get_calls())
    assert len(calls) == 1
    assert calls[0].inputs["name"] == "Bob"
    assert calls[0].inputs["age"] == 25
    assert calls[0].inputs["email"] == "bob@example.com"
    assert calls[0].output.name == "Bob"
    assert calls[0].output.age == 25
    assert calls[0].output.email == "bob@example.com"


def test_protobuf_list_input(client):
    @weave.op()
    def average_age(people: list[Person]) -> float:
        return sum(person.age for person in people) / len(people)

    people = [
        Person(name="Alice", age=30, email="alice@example.com"),
        Person(name="Bob", age=25, email="bob@example.com"),
        Person(name="Charlie", age=35, email="charlie@example.com"),
    ]
    result = average_age(people)
    assert pytest.approx(result) == 30.0

    calls = list(client.get_calls())
    assert len(calls) == 1
    assert calls[0].inputs["people"] == [
        Person(name="Alice", age=30, email="alice@example.com"),
        Person(name="Bob", age=25, email="bob@example.com"),
        Person(name="Charlie", age=35, email="charlie@example.com"),
    ]


def test_protobuf_dict_output(client):
    @weave.op()
    def person_to_dict(person: Person) -> dict:
        return {
            "name": person.name,
            "age": person.age,
            "email": person.email,
        }

    person = Person(name="David", age=40, email="david@example.com")
    result = person_to_dict(person)
    assert isinstance(result, dict)
    assert result == {
        "name": "David",
        "age": 40,
        "email": "david@example.com",
    }

    calls = list(client.get_calls())
    assert len(calls) == 1
    assert calls[0].inputs["person"].name == "David"
    assert calls[0].inputs["person"].age == 40
    assert calls[0].inputs["person"].email == "david@example.com"
    assert calls[0].output == {
        "name": "David",
        "age": 40,
        "email": "david@example.com",
    }
