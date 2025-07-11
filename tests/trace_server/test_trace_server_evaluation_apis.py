from unittest import mock
import weave
import pytest
from weave.trace_server.trace_server_interface import EvaluationStatusNotFound, EvaluationStatusReq, EvaluationStatusComplete, EvaluationStatusRunning
from weave.trace.weave_client import generate_id

@pytest.mark.asyncio
async def test_evaluation_status(client):
    
    eval_call_id = generate_id()
    
    def get_status():
        return client.server.evaluation_status(EvaluationStatusReq(project_id=client._project_id(), call_id=eval_call_id)).status
    
    @weave.op
    def model(a: int) -> int:
        assert get_status() == EvaluationStatusRunning(status="running", completed_rows=a-1, total_rows=3)
        return a + 1

    @weave.op
    def scorer(output: int, exp_output: int) -> float:
        return 1.0 if output == exp_output else 0.0

    dataset =  [{"a": 1, "exp_output": 2}, {"a": 2, "exp_output": 3}, {"a": 3, "exp_output": 4}]
    eval = weave.Evaluation(dataset=dataset, scorers=[scorer])
    
    assert get_status() == EvaluationStatusNotFound(status="pending")
    
    # mock weave.trace.env.py::get_weave_parallelism to return 1 (allows for checking status deterministically)
    with mock.patch("weave.trace.env.get_weave_parallelism", return_value=1):
        # Patch the first 2 calls to generate_id to return eval_call_id, then defer to the real function
        real_generate_id = generate_id
        def generate_id_side_effect():
            if generate_id_side_effect.calls < 2:
                generate_id_side_effect.calls += 1
                return eval_call_id
            return real_generate_id()
        generate_id_side_effect.calls = 0

        with mock.patch("weave.trace.weave_client.generate_id", side_effect=generate_id_side_effect):
            await eval.evaluate(model=model)

    assert get_status() == EvaluationStatusComplete(status="complete", completed_rows=3, total_rows=3)


