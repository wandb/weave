from typing import Any

from pydantic import BaseModel


class GuardrailResponse(BaseModel):
    safe: bool
    details: dict[str, Any]
