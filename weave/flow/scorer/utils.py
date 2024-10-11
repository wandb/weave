import json
from typing import Any

from pydantic import BaseModel


def stringify(model_output: Any) -> str:
    if isinstance(model_output, str):
        return model_output
    elif isinstance(model_output, (list, tuple)):
        return json.dumps(model_output, indent=2)
    elif isinstance(model_output, dict):
        return json.dumps(model_output, indent=2)
    elif isinstance(model_output, BaseModel):
        return model_output.model_dump_json(indent=2)
    else:
        raise ValueError(f"Unsupported model output type: {type(model_output)}")

if __name__ == "__main__":
    # test
    model_output = "hey"
    print(stringify(model_output))

    model_output = [1, 2, 3]
    print(stringify(model_output))

    model_output = {"a": 1, "b": 2}
    print(stringify(model_output))

    class TestModel(BaseModel):
        a: int
        b: str

    model_output = TestModel(a=1, b="test")
    print(stringify(model_output))
