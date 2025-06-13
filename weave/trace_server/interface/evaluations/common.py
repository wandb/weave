from typing import Any

from pydantic import BaseModel

JSONSchema = Any  # TODO: Type this better


class TypedSignature(BaseModel):
    input_schema: JSONSchema
    output_schema: JSONSchema
