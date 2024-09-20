import weave
import pytest
import PIL
from weave.trace.weave_client import WeaveClient

@pytest.mark.asyncio
async def test_evaluation_performance(client: WeaveClient):
    dataset = [
        {"question": "What is the capital of France?", "expected": "Paris"},
        {"question": "Who wrote 'To Kill a Mockingbird'?", "expected": "Harper Lee"},
        {"question": "What is the square root of 64?", "expected": "8"},
        {"question": "What is the thing you say when you don't know something?", "expected": "I don't know"},
    ]

    @weave.op()
    def predict(question: str):
        return "I don't know"
    
    @weave.op()
    def score(question: str, expected: str, model_output: str):
        return model_output == expected
    
    evaluation = weave.Evaluation(
        name="My Evaluation",
        dataset=dataset,
        scorers=[score],
    )

    log = [l for l in client.server.attribute_access_log if not l.startswith("_")]

    assert log == ['ensure_project_exists']

    # TODO: Client.pause "network" traffic

    res = await evaluation.evaluate(predict)
    assert res['score']['true_count'] == 1

    log = [l for l in client.server.attribute_access_log if not l.startswith("_")]

    assert log == ['ensure_project_exists']

    # TODO: Client.resume "network" traffic
    client._flush()

    assert "something interesting about the results" == False


