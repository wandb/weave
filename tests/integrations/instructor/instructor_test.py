import asyncio
import json
import os
from collections.abc import Iterable
from typing import Any

import pytest
from pydantic import BaseModel

import weave
from weave.integrations.integration_utilities import op_name_from_ref


class Person(BaseModel):
    person_name: str
    age: int


class User(BaseModel):
    user_name: str
    email: str
    twitter: str


class MeetingInfo(BaseModel):
    users: list[User]
    date: str
    location: str
    budget: int
    deadline: str


@pytest.mark.skip_clickhouse_client
@pytest.mark.vcr(
    filter_headers=["authorization", "x-api-key"],
    allowed_hosts=["api.wandb.ai", "localhost", "trace.wandb.ai"],
)
def test_instructor_openai(
    client: weave.trace.weave_client.WeaveClient,
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

    calls = list(client.calls())
    assert len(calls) == 2

    call = calls[0]
    assert call.started_at < call.ended_at
    assert op_name_from_ref(call.op_name) == "Instructor.create"
    output = call.output
    assert output.person_name == "John"
    assert output.age == 20

    call = calls[1]
    assert call.started_at < call.ended_at
    assert op_name_from_ref(call.op_name) == "openai.chat.completions.create"
    output = call.output
    output_arguments = json.loads(
        output["choices"][0]["message"]["tool_calls"][0]["function"]["arguments"]
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
def test_instructor_openai_with_completion(
    client: weave.trace.weave_client.WeaveClient,
) -> None:
    import instructor
    from openai import OpenAI

    api_key = os.environ.get("OPENAI_API_KEY", "DUMMY_API_KEY")
    lm_client = instructor.from_openai(OpenAI(api_key=api_key))
    person = lm_client.chat.completions.create_with_completion(
        model="gpt-3.5-turbo",
        response_model=Person,
        messages=[{"role": "user", "content": "My name is John and I am 20 years old"}],
    )

    calls = list(client.calls())
    assert len(calls) == 2

    call = calls[0]
    assert call.started_at < call.ended_at
    assert op_name_from_ref(call.op_name) == "Instructor.create_with_completion"

    call = calls[1]
    assert call.started_at < call.ended_at
    assert op_name_from_ref(call.op_name) == "openai.chat.completions.create"
    output = call.output
    output_arguments = json.loads(
        output["choices"][0]["message"]["tool_calls"][0]["function"]["arguments"]
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
    client: weave.trace.weave_client.WeaveClient,
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

    asyncio.run(extract_person("My name is John and I am 20 years old"))

    calls = list(client.calls())
    assert len(calls) == 2

    call = calls[0]
    assert call.started_at < call.ended_at
    assert op_name_from_ref(call.op_name) == "AsyncInstructor.create"
    output = call.output
    assert output.person_name == "John"
    assert output.age == 20

    call = calls[1]
    assert call.started_at < call.ended_at
    assert op_name_from_ref(call.op_name) == "openai.chat.completions.create"
    output = call.output
    output_arguments = json.loads(
        output["choices"][0]["message"]["tool_calls"][0]["function"]["arguments"]
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
    client: weave.trace.weave_client.WeaveClient,
) -> None:
    import instructor
    from openai import OpenAI

    api_key = os.environ.get("OPENAI_API_KEY", "DUMMY_API_KEY")
    lm_client = instructor.from_openai(
        OpenAI(api_key=api_key), mode=instructor.function_calls.Mode.JSON
    )
    lm_client.chat.completions.create(
        model="gpt-3.5-turbo-1106",
        temperature=0.1,
        response_model=Iterable[Person],
        stream=False,
        messages=[
            {
                "role": "user",
                "content": "Consider this data: Jason is 10 and John is 30.\
                             Correctly segment it into entities\
                            Make sure the JSON is correct",
            },
        ],
    )

    calls = list(client.calls())
    assert len(calls) == 2

    call = calls[0]
    assert call.started_at < call.ended_at
    assert op_name_from_ref(call.op_name) == "Instructor.create"
    output = call.output
    assert output[0].person_name == "Jason"
    assert output[0].age == 10
    assert output[1].person_name == "John"
    assert output[1].age == 30

    call = calls[1]
    assert call.started_at < call.ended_at
    assert op_name_from_ref(call.op_name) == "openai.chat.completions.create"
    output = call.output
    output_arguments = json.loads(output["choices"][0]["message"]["content"])
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
    client: weave.trace.weave_client.WeaveClient,
) -> None:
    import instructor
    from openai import OpenAI

    api_key = os.environ.get("OPENAI_API_KEY", "DUMMY_API_KEY")
    lm_client = instructor.from_openai(
        OpenAI(api_key=api_key), mode=instructor.Mode.TOOLS
    )
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
                "content": "Extract `Jason is 10 and John is 30`",
            },
        ],
    )
    _ = list(users)

    calls = list(client.calls())
    assert len(calls) == 2

    call = calls[0]
    assert call.started_at < call.ended_at
    assert op_name_from_ref(call.op_name) == "Instructor.create"
    output = call.output
    assert output[0].person_name == "Jason"
    assert output[0].age == 10
    assert output[1].person_name == "John"
    assert output[1].age == 30

    call = calls[1]
    assert call.started_at < call.ended_at
    assert op_name_from_ref(call.op_name) == "openai.chat.completions.create"


@pytest.mark.skip_clickhouse_client
@pytest.mark.vcr(
    filter_headers=["authorization", "x-api-key"],
    allowed_hosts=["api.wandb.ai", "localhost", "trace.wandb.ai"],
)
def test_instructor_iterable_async_stream(
    client: weave.trace.weave_client.WeaveClient,
) -> None:
    import instructor
    from openai import AsyncOpenAI

    api_key = os.environ.get("OPENAI_API_KEY", "DUMMY_API_KEY")
    lm_client = instructor.from_openai(
        AsyncOpenAI(api_key=api_key), mode=instructor.Mode.TOOLS
    )

    async def print_iterable_results() -> list[Person]:
        model = await lm_client.chat.completions.create(
            model="gpt-4",
            response_model=Iterable[Person],
            max_retries=2,
            stream=True,
            messages=[
                {
                    "role": "system",
                    "content": "You are a perfect entity extraction system",
                },
                {
                    "role": "user",
                    "content": "Extract `Jason is 10 and John is 30`",
                },
            ],
        )
        return [m async for m in model]

    asyncio.run(print_iterable_results())

    calls = list(client.calls())
    assert len(calls) == 2

    call = calls[0]
    assert call.exception is None and call.ended_at is not None
    assert call.started_at < call.ended_at
    assert op_name_from_ref(call.op_name) == "AsyncInstructor.create"
    output = call.output
    assert output[0].person_name == "Jason"
    assert output[0].age == 10
    assert output[1].person_name == "John"
    assert output[1].age == 30

    call = calls[1]
    assert call.exception is None and call.ended_at is not None
    assert call.started_at < call.ended_at
    assert op_name_from_ref(call.op_name) == "openai.chat.completions.create"


@pytest.mark.skip_clickhouse_client
@pytest.mark.vcr(
    filter_headers=["authorization", "x-api-key"],
    allowed_hosts=["api.wandb.ai", "localhost", "trace.wandb.ai"],
)
def test_instructor_partial_stream(
    client: weave.trace.weave_client.WeaveClient,
) -> None:
    import instructor
    from openai import OpenAI

    api_key = os.environ.get("OPENAI_API_KEY", "DUMMY_API_KEY")
    lm_client = instructor.from_openai(OpenAI(api_key=api_key))
    text_block = """
In our recent online meeting, participants from various backgrounds joined to discuss the upcoming tech
conference. The names and contact details of the participants were as follows:

- Name: John Doe, Email: johndoe@email.com, Twitter: @TechGuru44
- Name: Jane Smith, Email: janesmith@email.com, Twitter: @DigitalDiva88
- Name: Alex Johnson, Email: alexj@email.com, Twitter: @CodeMaster2023

During the meeting, we agreed on several key points. The conference will be held on March 15th, 2024,
at the Grand Tech Arena located at 4521 Innovation Drive. Dr. Emily Johnson, a renowned AI researcher,
will be our keynote speaker.

The budget for the event is set at $50,000, covering venue costs, speaker fees, and promotional activities.
Each participant is expected to contribute an article to the conference blog by February 20th.

A follow-up meeting is scheduled for January 25th at 3 PM GMT to finalize the agenda and confirm the
list of speakers.
    """
    extraction_stream = lm_client.chat.completions.create_partial(
        model="gpt-4",
        response_model=MeetingInfo,
        messages=[
            {
                "role": "user",
                "content": f"Get the information about the meeting and the users {text_block}",
            },
        ],
        stream=True,
    )
    _ = list(extraction_stream)

    calls = list(client.calls())
    assert len(calls) == 2

    call = calls[0]
    assert call.exception is None and call.ended_at is not None
    assert call.started_at < call.ended_at
    assert op_name_from_ref(call.op_name) == "Instructor.create_partial"
    output = call.output
    assert output.users[0].user_name == "John Doe"
    assert output.users[0].email == "johndoe@email.com"
    assert output.users[0].twitter == "@TechGuru44"
    assert output.users[1].user_name == "Jane Smith"
    assert output.users[1].email == "janesmith@email.com"
    assert output.users[1].twitter == "@DigitalDiva88"
    assert output.users[2].user_name == "Alex Johnson"
    assert output.users[2].email == "alexj@email.com"
    assert output.users[2].twitter == "@CodeMaster2023"

    call = calls[1]
    assert call.exception is None and call.ended_at is not None
    assert call.started_at < call.ended_at
    assert op_name_from_ref(call.op_name) == "openai.chat.completions.create"


@pytest.mark.skip_clickhouse_client
@pytest.mark.vcr(
    filter_headers=["authorization", "x-api-key"],
    allowed_hosts=["api.wandb.ai", "localhost", "trace.wandb.ai"],
)
def test_instructor_partial_stream_async(
    client: weave.trace.weave_client.WeaveClient,
) -> None:
    import instructor
    from openai import AsyncOpenAI

    api_key = os.environ.get("OPENAI_API_KEY", "DUMMY_API_KEY")
    lm_client = instructor.from_openai(AsyncOpenAI(api_key=api_key))
    text_block = """
In our recent online meeting, participants from various backgrounds joined to discuss the upcoming tech
conference. The names and contact details of the participants were as follows:

- Name: John Doe, Email: johndoe@email.com, Twitter: @TechGuru44
- Name: Jane Smith, Email: janesmith@email.com, Twitter: @DigitalDiva88
- Name: Alex Johnson, Email: alexj@email.com, Twitter: @CodeMaster2023

During the meeting, we agreed on several key points. The conference will be held on March 15th, 2024,
at the Grand Tech Arena located at 4521 Innovation Drive. Dr. Emily Johnson, a renowned AI researcher,
will be our keynote speaker.

The budget for the event is set at $50,000, covering venue costs, speaker fees, and promotional activities.
Each participant is expected to contribute an article to the conference blog by February 20th.

A follow-up meeting is scheduled for January 25th at 3 PM GMT to finalize the agenda and confirm the
list of speakers.
    """

    async def fetch_results(text_block: str) -> list[Any]:
        extraction_stream = lm_client.chat.completions.create_partial(
            model="gpt-4",
            response_model=MeetingInfo,
            messages=[
                {
                    "role": "user",
                    "content": f"Get the information about the meeting and the users {text_block}",
                },
            ],
            stream=True,
        )
        return [extraction async for extraction in extraction_stream]

    _ = asyncio.run(fetch_results(text_block))

    calls = list(client.calls())
    assert len(calls) == 2

    call = calls[0]
    assert call.exception is None and call.ended_at is not None
    assert call.started_at < call.ended_at
    assert op_name_from_ref(call.op_name) == "AsyncInstructor.create_partial"
    output = call.output
    assert output.users[0].user_name == "John Doe"
    assert output.users[0].email == "johndoe@email.com"
    assert output.users[0].twitter == "@TechGuru44"
    assert output.users[1].user_name == "Jane Smith"
    assert output.users[1].email == "janesmith@email.com"
    assert output.users[1].twitter == "@DigitalDiva88"
    assert output.users[2].user_name == "Alex Johnson"
    assert output.users[2].email == "alexj@email.com"
    assert output.users[2].twitter == "@CodeMaster2023"

    call = calls[1]
    assert call.exception is None and call.ended_at is not None
    assert call.started_at < call.ended_at
    assert op_name_from_ref(call.op_name) == "openai.chat.completions.create"
