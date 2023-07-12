from .. import decorator_type


@decorator_type.type(
    "stream_table",
)
class StreamTableType:
    table_name: str  # maps to run name in W&B data model
    project_name: str
    entity_name: str
