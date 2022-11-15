# See mappers_python_def for actual implementation. Split into two
# to resolve circular dependency.
import typing

if typing.TYPE_CHECKING:
    from . import mappers
    from . import artifacts_local
    from . import weave_types


def map_to_python(
    type_: "weave_types.Type",
    artifact: "artifacts_local.Artifact",
    path: list[str] = [],
) -> "mappers.Mapper":
    pass


def map_from_python(
    type_: "weave_types.Type",
    artifact: "artifacts_local.Artifact",
    path: list[str] = [],
) -> "mappers.Mapper":
    pass
