import asyncio
import json
import os
from typing import Any, Iterable, Optional

import pytest
from pydantic import BaseModel

import weave
from weave.trace_server import trace_server_interface as tsi


def _get_call_output(call: tsi.CallSchema) -> Any:
    """This is a hack and should not be needed. We should be able to auto-resolve this for the user.

    Keeping this here for now, but it should be removed in the future once we have a better solution.
    """
    call_output = call.output
    if isinstance(call_output, str) and call_output.startswith("weave://"):
        return weave.ref(call_output).get()
    return call_output


def flatten_calls(
    calls: list[tsi.CallSchema], parent_id: Optional[str] = None, depth: int = 0
) -> list:
    def children_of_parent_id(id: Optional[str]) -> list[tsi.CallSchema]:
        return [call for call in calls if call.parent_id == id]

    children = children_of_parent_id(parent_id)
    res = []
    for child in children:
        res.append((child, depth))
        res.extend(flatten_calls(calls, child.id, depth + 1))

    return res


def op_name_from_ref(ref: str) -> str:
    return ref.split("/")[-1].split(":")[0]


class Person(BaseModel):
    person_name: str
    age: int


@pytest.mark.skip_clickhouse_client
@pytest.mark.vcr(
    filter_headers=["authorization", "x-api-key"],
    allowed_hosts=["api.wandb.ai", "localhost", "trace.wandb.ai"],
)
def test_instructor_openai(
    client: weave.weave_client.WeaveClient,
) -> None:
    import instructor
    from openai import OpenAI

    api_key = os.environ.get("OPENAI_API_KEY", "DUMMY_API_KEY")
    lm_client = instructor.from_openai(OpenAI(api_key=api_key))
    person = lm_client.chat.completions.create(
        model="gpt-3.5-turbo",
        response_model=Person,
        messages=[{"role": "user", "content": "My name is John and I am 20 years old"}],
    )
    assert person.person_name == "John"
    assert person.age == 20

    weave_server_response = client.server.calls_query(
        tsi.CallsQueryReq(project_id=client._project_id())
    )
    assert len(weave_server_response.calls) == 2

    flattened_calls_list = [
        (op_name_from_ref(c.op_name), d)
        for (c, d) in flatten_calls(weave_server_response.calls)
    ]
    assert flattened_calls_list == [
        ("Instructor.create", 0),
        ("openai.chat.completions.create", 1),
    ]

    call = weave_server_response.calls[0]
    assert call.exception is None and call.ended_at is not None
    output = _get_call_output(call)
    assert output.person_name == "John"
    assert output.age == 20

    call = weave_server_response.calls[1]
    assert call.exception is None and call.ended_at is not None
    output = _get_call_output(call)
    output_arguments = json.loads(
        output.choices[0].message.tool_calls[0].function._val.arguments
    )
    assert "person_name" in output_arguments
    assert "age" in output_arguments
    assert "John" in output_arguments["person_name"]
    assert output_arguments["age"] == 20


@pytest.mark.skip_clickhouse_client
@pytest.mark.vcr(
    filter_headers=["authorization", "x-api-key"],
    allowed_hosts=["api.wandb.ai", "localhost", "trace.wandb.ai"],
)
def test_instructor_openai_async(
    client: weave.weave_client.WeaveClient,
) -> None:
    import instructor
    from openai import AsyncOpenAI

    api_key = os.environ.get("OPENAI_API_KEY", "DUMMY_API_KEY")
    lm_client = instructor.from_openai(AsyncOpenAI(api_key=api_key))

    async def extract_person(text: str) -> Person:
        return await lm_client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "user", "content": text},
            ],
            response_model=Person,
        )

    person = asyncio.run(extract_person("My name is John and I am 20 years old"))

    assert person.person_name == "John"
    assert person.age == 20

    weave_server_response = client.server.calls_query(
        tsi.CallsQueryReq(project_id=client._project_id())
    )
    assert len(weave_server_response.calls) == 2

    flattened_calls_list = [
        (op_name_from_ref(c.op_name), d)
        for (c, d) in flatten_calls(weave_server_response.calls)
    ]
    assert flattened_calls_list == [
        ("AsyncInstructor.create", 0),
        ("openai.chat.completions.create", 1),
    ]

    call = weave_server_response.calls[0]
    assert call.exception is None and call.ended_at is not None
    output = _get_call_output(call)
    assert output.person_name == "John"
    assert output.age == 20

    call = weave_server_response.calls[1]
    assert call.exception is None and call.ended_at is not None
    output = _get_call_output(call)
    output_arguments = json.loads(
        output.choices[0].message.tool_calls[0].function._val.arguments
    )
    assert "person_name" in output_arguments
    assert "age" in output_arguments
    assert "John" in output_arguments["person_name"]
    assert output_arguments["age"] == 20


@pytest.mark.skip_clickhouse_client
@pytest.mark.vcr(
    filter_headers=["authorization", "x-api-key"],
    allowed_hosts=["api.wandb.ai", "localhost", "trace.wandb.ai"],
)
def test_instructor_iterable(
    client: weave.weave_client.WeaveClient,
) -> None:
    import instructor
    from openai import OpenAI

    lm_client = instructor.from_openai(
        OpenAI(), mode=instructor.function_calls.Mode.JSON
    )
    users = lm_client.chat.completions.create(
        model="gpt-3.5-turbo-1106",
        temperature=0.1,
        response_model=Iterable[Person],
        stream=False,
        messages=[
            {
                "role": "user",
                "content": "Consider this data: Jason is 10 and John is 30.\
                             Correctly segment it into entitites\
                            Make sure the JSON is correct",
            },
        ],
    )

    assert users[0].person_name == "Jason"
    assert users[0].age == 10
    assert users[1].person_name == "John"
    assert users[1].age == 30

    weave_server_response = client.server.calls_query(
        tsi.CallsQueryReq(project_id=client._project_id())
    )
    assert len(weave_server_response.calls) == 2

    flattened_calls_list = [
        (op_name_from_ref(c.op_name), d)
        for (c, d) in flatten_calls(weave_server_response.calls)
    ]
    assert flattened_calls_list == [
        ("Instructor.create", 0),
        ("openai.chat.completions.create", 1),
    ]

    call = weave_server_response.calls[0]
    assert call.exception is None and call.ended_at is not None
    output = _get_call_output(call)
    output = [weave.ref(reference).get() for reference in output]
    assert output[0].person_name == "Jason"
    assert output[0].age == 10
    assert output[1].person_name == "John"
    assert output[1].age == 30

    call = weave_server_response.calls[1]
    assert call.exception is None and call.ended_at is not None
    output = _get_call_output(call)
    output_arguments = json.loads(output.choices[0].message.content)
    assert "tasks" in output_arguments
    assert "person_name" in output_arguments["tasks"][0]
    assert "age" in output_arguments["tasks"][0]
    assert "Jason" in output_arguments["tasks"][0]["person_name"]
    assert output_arguments["tasks"][0]["age"] == 10
    assert "person_name" in output_arguments["tasks"][1]
    assert "age" in output_arguments["tasks"][1]
    assert "John" in output_arguments["tasks"][1]["person_name"]
    assert output_arguments["tasks"][1]["age"] == 30


@pytest.mark.skip_clickhouse_client
@pytest.mark.vcr(
    filter_headers=["authorization", "x-api-key"],
    allowed_hosts=["api.wandb.ai", "localhost", "trace.wandb.ai"],
)
def test_instructor_iterable_sync_stream(
    client: weave.weave_client.WeaveClient,
) -> None:
    import instructor
    from openai import OpenAI

    lm_client = instructor.from_openai(OpenAI(), mode=instructor.Mode.TOOLS)
    users = lm_client.chat.completions.create(
        model="gpt-4",
        stream=True,
        response_model=Iterable[Person],
        messages=[
            {
                "role": "system",
                "content": "You are a perfect entity extraction system",
            },
            {
                "role": "user",
                "content": ("Extract `Jason is 10 and John is 30`"),
            },
        ],
    )
    users = [user for user in users]
    assert users[0].person_name == "Jason"
    assert users[0].age == 10
    assert users[1].person_name == "John"
    assert users[1].age == 30

    weave_server_response = client.server.calls_query(
        tsi.CallsQueryReq(project_id=client._project_id())
    )
    assert len(weave_server_response.calls) == 2

    flattened_calls_list = [
        (op_name_from_ref(c.op_name), d)
        for (c, d) in flatten_calls(weave_server_response.calls)
    ]
    assert flattened_calls_list == [
        ("Instructor.create", 0),
        ("openai.chat.completions.create", 1),
    ]

    call = weave_server_response.calls[0]
    assert call.exception is None and call.ended_at is not None
    output = _get_call_output(call)
    output = [weave.ref(reference).get() for reference in output]
    assert output[0].person_name == "Jason"
    assert output[0].age == 10
    assert output[1].person_name == "John"
    assert output[1].age == 30

    call = weave_server_response.calls[1]
    assert call.exception is None and call.ended_at is not None
    output = _get_call_output(call)
    output_arguments = json.loads(
        output["choices"][0]["message"]["tool_calls"][0]["function"]["arguments"]
    )
    assert "tasks" in output_arguments
    assert "person_name" in output_arguments["tasks"][0]
    assert "age" in output_arguments["tasks"][0]
    assert "Jason" in output_arguments["tasks"][0]["person_name"]
    assert output_arguments["tasks"][0]["age"] == 10
    assert "person_name" in output_arguments["tasks"][1]
    assert "age" in output_arguments["tasks"][1]
    assert "John" in output_arguments["tasks"][1]["person_name"]
    assert output_arguments["tasks"][1]["age"] == 30
