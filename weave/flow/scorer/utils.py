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
