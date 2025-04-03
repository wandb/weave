from pydantic import Field, field_validator
from typing_extensions import Self

from weave.flow.casting import ScorerLike
from weave.flow.obj import Object
from weave.trace.api import ObjectRef, publish
from weave.trace.objectify import register_object
from weave.trace.vals import WeaveObject


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
        call_filter={
            "op_names": ["my_op"],
            "query": {
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

    sampling_rate: float = Field(ge=0, le=1)
    scorers: list[ScorerLike]
    call_filter: dict
    active: bool = False

    @field_validator("call_filter")
    @classmethod
    def _validate_call_filter(cls, call_filter: dict) -> dict:
        """
        Example filter:
        {
            "op_names": [
                "weave:///wandb/directeur-sportif/op/query_model:*"
            ],
            "query":{
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
        }
        """
        if not isinstance(call_filter, dict):
            raise ValueError("call_filter must be a dictionary")  # noqa: TRY004

        if "op_names" not in call_filter:
            raise ValueError("call_filter must contain an op_names key")

        if not isinstance(call_filter["op_names"], list):
            raise ValueError("op_names must be a list")  # noqa: TRY004

        if "query" in call_filter:
            if "$expr" not in call_filter["query"]:
                raise ValueError("call_filter must contain a $expr key")

        return call_filter

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
                field_values[field_name] = getattr(obj, field_name)

        return cls(**field_values)
