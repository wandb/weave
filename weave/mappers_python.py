# See mappers_python_def for actual implementation. Split into two
# to resolve circular dependency.
import typing

if typing.TYPE_CHECKING:
    from . import mappers
    from . import artifact_base
    from . import weave_types


def map_to_python(  # type: ignore[empty-body]
    type_: "weave_types.Type",
    artifact: "artifact_base.Artifact",
    path: list[str] = [],
    mapper_options: typing.Any = None,
) -> "mappers.Mapper":
    pass


def map_from_python(  # type: ignore[empty-body]
    type_: "weave_types.Type",
    artifact: "artifact_base.Artifact",
    path: list[str] = [],
    mapper_options: typing.Any = None,
) -> "mappers.Mapper":
    pass
