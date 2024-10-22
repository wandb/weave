from weave.flow.util import map_nested_dict


def test_map_nested_dict():
    mapping = {
        "inputs.model": "model",
        "inputs.example.prompt": "input.prompt",
        "outputs.prediction": "output.prediction",
    }

    input_dict = {
        "inputs": {
            "model": "gpt-3.5-turbo",
            "example": {"prompt": "What is the capital of France?"},
        },
        "outputs": {"prediction": "The capital of France is Paris."},
    }

    mapped_dict = map_nested_dict(input_dict, mapping)
    expected_output = {
        "model": "gpt-3.5-turbo",
        "input": {"prompt": "What is the capital of France?"},
        "output": {"prediction": "The capital of France is Paris."},
    }

    assert mapped_dict == expected_output
