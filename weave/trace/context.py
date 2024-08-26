import contextvars
from typing import Any

call_attributes: contextvars.ContextVar[dict[str, Any]] = contextvars.ContextVar(
    "call_attributes", default={}
)
