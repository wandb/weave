import weave


def test_call_to_dict(client):
    # Step 1: Define a simple op so we can create a real traced call object.
    @weave.op
    def greet(name: str, age: int) -> str:
        return f"Hello {name}, you are {age}!"

    # Step 2: Execute the op and capture the resulting Call instance.
    _, call = greet.call("Alice", 30)

    # Step 3: Verify that to_dict() includes all expected serialized fields,
    # including wb_run_* and storage size metadata fields.
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
        "thread_id": call.thread_id,
        "turn_id": call.turn_id,
        "project_id": call.project_id,
        "wb_run_id": call.wb_run_id,
        "wb_run_step": call.wb_run_step,
        "wb_run_step_end": call.wb_run_step_end,
        "storage_size_bytes": call.storage_size_bytes,
        "total_storage_size_bytes": call.total_storage_size_bytes,
    }
