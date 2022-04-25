from ..api import op, weave_class
from .. import weave_types as types
from ..ops_primitives import file as weave_file

from wandb.apis import public as wandb_api
from wandb.sdk.interface import artifacts as wandb_artifacts


class ArtifactVersionFileType(types.Type):
    name = "artifactversion-path"
    instance_classes = wandb_artifacts.ArtifactEntry

    def instance_to_dict(self, obj):
        art = obj.parent_artifact()
        return {
            "entity_name": art.entity,
            "project_name": art.project,
            "artifact_name": art._sequence_name,
            "artifact_version": art.version,
            "path": obj.name,
        }

    def instance_from_dict(self, d):
        api = wandb_api.Api()
        return api.artifact(
            "%s/%s/%s:%s"
            % (
                d["entity_name"],
                d["project_name"],
                d["artifact_name"],
                d["artifact_version"],
            )
        ).get_path(d["path"])


@weave_class(weave_type=ArtifactVersionFileType)
class ArtifactVersionFile(weave_file.File):
    @op(
        name="artifactVersionPath-contents",
        input_type={"artifactVersionPath": ArtifactVersionFileType()},
        output_type=types.String(),
    )
    def contents(artifactVersionPath):
        local_path = artifactVersionPath.download()
        return open(local_path, encoding="ISO-8859-1").read()
