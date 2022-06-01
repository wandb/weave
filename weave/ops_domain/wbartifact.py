from wandb.apis import public as wandb_api

from ..api import op, weave_class
from .. import weave_types as types
from . import file_wbartifact
from ..wandb_api import wandb_public_api


class ArtifactVersionType(types.Type):
    name = "artifactVersion"
    instance_classes = wandb_api.Artifact
    instance_class = wandb_api.Artifact

    def instance_to_dict(self, obj):
        return {
            "entity_name": obj.entity,
            "project_name": obj.project,
            "artifact_name": obj._sequence_name,
            "artifact_version": obj.version,
        }

    def instance_from_dict(self, d):
        api = wandb_public_api()
        return api.artifact(
            "%s/%s/%s:%s"
            % (
                d["entity_name"],
                d["project_name"],
                d["artifact_name"],
                d["artifact_version"],
            )
        )


@weave_class(weave_type=ArtifactVersionType)
class ArtifactVersion:
    @op(
        name="artifactVersion-fileReturnType",
        input_type={"artifactVersion": ArtifactVersionType(), "path": types.String()},
        output_type=types.Type(),
    )
    def path_type(artifactVersion, path):
        try:
            artifactVersion.get_path(path)
        except KeyError:
            return types.DirType()
        parts = path.split(".")
        ext = ""
        wb_object_type = types.NoneType()
        if len(parts) != 1:
            ext = parts[-1]
        if len(parts) > 2 and ext == "json":
            wb_object_type = types.Const(types.String(), parts[-2])
        return types.FileType(
            extension=types.Const(types.String(), ext), wb_object_type=wb_object_type
        )

    @op(
        name="artifactVersion-file",
        input_type={"artifactVersion": ArtifactVersionType(), "path": types.String()},
        # TODO: This Type is not complete (missing DirType())
        # TODO: This needs to call ArtifactVersion.path_type()
        output_type=file_wbartifact.ArtifactVersionFileType(),
    )
    # TODO: This function should probably be called path, but it return Dir or File.
    # ok...
    def path(artifactVersion, path):
        return artifactVersion.read_path(path)


@op(
    name="asset-artifactVersion",
    input_type={"asset": types.Any()},
    output_type=ArtifactVersionType(),
)
def artifactVersion(asset):
    return asset.artifact
