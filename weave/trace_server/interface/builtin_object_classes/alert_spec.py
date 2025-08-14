import datetime
from typing import Optional

from pydantic import BaseModel, Field

from weave.trace_server.interface.builtin_object_classes import base_object_def


class TimeWindow(BaseModel):
    type: str = "time"
    duration: str = Field(enum=["1m", "5m", "10m", "1h", "1d", "1w"])


class CountWindow(BaseModel):
    type: str = "count"
    count: int = Field(
        default=10,
        ge=0,
        le=1001,
        examples=[1, 10, 100, 1000],
    )


WindowType = TimeWindow | CountWindow


class AlertSpec(base_object_def.BaseObject):
    op_scope: Optional[list[str]] = Field(
        default=None,
        examples=[["weave:///entity/project/op/name:digest"]],
    )
    metric_type: str = Field(enum=["score", "trace"])
    metric_name: str = Field(
        examples=[
            "output.f1score",
            "output.scores.accuracy",
            "f1score",  # feedback scorer?
        ]
    )
    threshold: float = Field(examples=[0.1, 99.0])
    direction: str = Field(enum=[">", ">=", "=", "<=", "<"])
    window: WindowType = Field(
        examples=[
            {"type": "time", "duration": "1h"},
            {"type": "count", "count": 100},
        ]
    )

    # Controls muting, by default is None
    # When set and > now(), is filtered out of alerting
    # Also can be far in the future to turn off an alert w/o deleting
    mute_until: Optional[datetime.datetime] = Field(default=None)
