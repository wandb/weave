import json
from typing import Any

from pydantic import BaseModel


def stringify(output: Any) -> str:
    if isinstance(output, str):
        return output
    elif isinstance(output, (list, tuple)):
        return json.dumps(output, indent=2)
    elif isinstance(output, dict):
        return json.dumps(output, indent=2)
    elif isinstance(output, BaseModel):
        return output.model_dump_json(indent=2)
    else:
        raise ValueError(f"Unsupported model output type: {type(output)}")


if __name__ == "__main__":
    # test
    output = "hey"
    print(stringify(output))

    output = [1, 2, 3]
    print(stringify(output))

    output = {"a": 1, "b": 2}
    print(stringify(output))

    class TestModel(BaseModel):
        a: int
        b: str

    output = TestModel(a=1, b="test")
    print(stringify(output))
