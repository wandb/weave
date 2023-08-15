import typing
from .. import decorator_type


class Hints(typing.TypedDict):
    integrations: list[str]


@decorator_type.type(
    "stream_table",
)
class StreamTableObj:
    table_name: str  # maps to run name in W&B data model
    project_name: str
    entity_name: str
    hints: typing.Optional[Hints]
