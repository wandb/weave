from typing import Any

from pydantic import BaseModel

JSONSchema = Any  # TODO: Type this better


class TypedSignature(BaseModel):
    input_type: JSONSchema
    output_type: JSONSchema
