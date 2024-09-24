# See mappers_python_def for actual implementation. Split into two
# to resolve circular dependency.
import typing

if typing.TYPE_CHECKING:
    from weave_query.weave_query import artifact_base, mappers, weave_types


def map_to_python(  # type: ignore[empty-body]
    type_: "weave_types.Type",
    artifact: "artifact_base.Artifact",
    path: list[str] = [],
    mapper_options: typing.Any = None,
) -> "mappers.Mapper":
    raise NotImplementedError


def map_from_python(  # type: ignore[empty-body]
    type_: "weave_types.Type",
    artifact: "artifact_base.Artifact",
    path: list[str] = [],
    mapper_options: typing.Any = None,
) -> "mappers.Mapper":
    raise NotImplementedError
