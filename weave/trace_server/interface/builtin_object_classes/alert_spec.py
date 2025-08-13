from typing import Any, Optional

import jsonschema
from pydantic import BaseModel, Field, create_model, field_validator, model_validator
from pydantic.fields import FieldInfo

from weave.trace_server.interface.builtin_object_classes import base_object_def

SUPPORTED_PRIMITIVES = (int, float, bool, str)


class AlertSpec(base_object_def.BaseObject):
    spec: dict[str, Any] = Field(default_factory=dict)

    # If provided, this feedback type will only be shown
    # when a call is generated from the given op ref
    op_scope: Optional[list[str]] = Field(default=None)
