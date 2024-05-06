from ...trace_server import trace_server_interface as tsi
from weave import autopatch


def run_user_code():
    import instructor
    from pydantic import BaseModel
    from openai import OpenAI
    import weave

    # Define your desired output structure
    class UserInfo(BaseModel):
        name: str
        age: int

    # Patch the OpenAI client
    client = instructor.patch(OpenAI())

    @weave.op()
    def instructor_op():
        # Extract structured data from natural language
        user_info = client.chat.completions.create(
            model="gpt-3.5-turbo",
            response_model=UserInfo,
            messages=[{"role": "user", "content": "John Doe is 30 years old."}],
        )

        print(user_info.name)
        # > John Doe
        print(user_info.age)

    instructor_op()


def test_instructor(client):
    # TODO: Move this to a fixture, currently the `client` fixture does
    # not call `weave_init` directly so the autopatching is not done.
    autopatch.autopatch()
    run_user_code()

    inner_res = client.server.calls_query(
        tsi.CallsQueryReq(
            project_id=client._project_id(),
        )
    )

    # Of course, we might want to assert more than just the number of calls,
    # for example, the actual content of the calls.
    assert len(inner_res.calls) == 2
