from typing import Any

from pydantic import Field

from weave.trace_server.interface.builtin_object_classes import base_object_def


class AlertSpec(base_object_def.BaseObject):
    # If provided, this alert will only apply to calls from the given op refs
    op_scope: list[str] | None = Field(
        default=None,
        examples=[
            ["weave:///entity/project/op/name:digest"],
            ["weave:///entity/project/op/name:*"],
        ],
    )

    # Flexible alert specification (threshold config, window config, etc.)
    spec: dict[str, Any] = Field(default_factory=dict)
