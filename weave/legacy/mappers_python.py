# See mappers_python_def for actual implementation. Split into two
# to resolve circular dependency.
import typing

if typing.TYPE_CHECKING:
    from weave import weave_types
    from weave.legacy import artifact_base, mappers


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
