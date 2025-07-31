from typing import Optional

from pydantic import Field
from typing_extensions import Self

from weave.flow.casting import Scorer
from weave.flow.obj import Object
from weave.trace.api import ObjectRef, publish
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
        return cls.model_validate(obj.unwrap())
