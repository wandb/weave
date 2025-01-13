from pydantic import BaseModel


class GuardrailResponse(BaseModel):
    safe: bool
    summary: str
