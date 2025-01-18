import weave


def test_call_to_dict(client):
    @weave.op
    def greet(name: str, age: int) -> str:
        return f"Hello {name}, you are {age}!"

    _, call = greet.call("Alice", 30)
    assert call.to_dict() == {
        "op_name": call.op_name,
        "display_name": call.display_name,
        "inputs": call.inputs,
        "output": call.output,
        "exception": call.exception,
        "summary": call.summary,
        "attributes": call.attributes,
        "started_at": call.started_at,
        "ended_at": call.ended_at,
        "deleted_at": call.deleted_at,
        "id": call.id,
        "parent_id": call.parent_id,
        "trace_id": call.trace_id,
        "project_id": call.project_id,
    }
