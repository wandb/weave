from ..decorator_type import type

@type()
class StreamTableType:
    entity_name: str
    project_name: str
    table_name: str
