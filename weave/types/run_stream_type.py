from .. import decorator_type


@decorator_type.type(
    "run_stream",
)
class RunStreamType:
    entity_name: str
    project_name: str
    run_name: str
