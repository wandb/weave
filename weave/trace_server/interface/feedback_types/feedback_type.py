from typing import Type

from pydantic import BaseModel


class FeedbackType(BaseModel):
    name: str
    payload_spec: Type[BaseModel]
