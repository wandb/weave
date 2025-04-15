from typing import Any, Optional

from pydantic import Field
from typing_extensions import Self

from weave.flow.casting import Scorer
from weave.flow.obj import Object
from weave.trace.api import ObjectRef, publish
from weave.trace.object_record import ObjectRecord
from weave.trace.objectify import register_object
from weave.trace.vals import WeaveObject
from weave.trace_server.interface.query import Query


@register_object
class Monitor(Object):
    """
    Sets up a monitor to score incoming calls automatically.

    Examples:

    ```python
    import weave
    from weave.scorers import ValidJSONScorer

    json_scorer = ValidJSONScorer()

    my_monitor = weave.Monitor(
        name="my-monitor",
        description="This is a test monitor",
        sampling_rate=0.5,
        op_names=["my_op"],
        query={
            "$expr": {
                "$gt": [
                    {
                            "$getField": "started_at"
                        },
                        {
                            "$literal": 1742540400
                        }
                    ]
                }
            }
        },
        scorers=[json_scorer],
    )

    my_monitor.activate()
    ```
    """

    sampling_rate: float = Field(ge=0, le=1, default=1)
    scorers: list[Scorer]
    op_names: list[str]
    query: Optional[Query] = None
    active: bool = False

    def activate(self) -> ObjectRef:
        """Activates the monitor.

        Returns:
            The ref to the monitor.
        """
        self.active = True
        self.ref = None
        return publish(self)

    def deactivate(self) -> ObjectRef:
        """Deactivates the monitor.

        Returns:
            The ref to the monitor.
        """
        self.active = False
        self.ref = None
        return publish(self)

    @classmethod
    def from_obj(cls, obj: WeaveObject) -> Self:
        field_values = {}
        for field_name in cls.model_fields:
            if hasattr(obj, field_name):
                field_obj = getattr(obj, field_name)

                # Special-casing the query field to convert
                # a WeaveObject(ObjectRecord(...)) to a Query
                if field_name == "query":
                    field_obj = Query(**_obj_rec_to_query_dict(field_obj._val))

                field_values[field_name] = field_obj

        return cls(**field_values)


def _obj_rec_to_query_dict(obj: ObjectRecord) -> dict:
    """Converts an ObjectRecord to a dictionary that can be used to create a Query."""

    def _treat_value(v: Any) -> Any:
        if isinstance(v, ObjectRecord):
            return _obj_rec_to_query_dict(v)
        elif isinstance(v, list):
            return [_treat_value(i) for i in v]
        elif isinstance(v, dict):
            return {k: _treat_value(v) for k, v in v.items()}
        else:
            return v

    def _snake_to_camel(snake_str: str) -> str:
        components = snake_str.split("_")
        return components[0] + "".join(x.title() for x in components[1:])

    def _treat_key(k: str) -> str:
        return f"${_snake_to_camel(k[:-1])}"

    return {
        _treat_key(k): _treat_value(v)
        for k, v in obj.__dict__.items()
        if k != "_class_name" and k != "_bases"
    }
