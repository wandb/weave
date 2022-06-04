import os
from ..api import op, weave_class
from .. import weave_types as types
from ..ops_primitives import file as weave_file
from .. import artifacts_local

from .. import wandb_api
from wandb.apis import public as wandb_public


class ArtifactVersionFileType(types.FileType):
    name = "artifactversion-path"

    def property_types(self):
        return {
            "entity_name": types.String(),
            "project_name": types.String(),
            "artifact_name": types.String(),
            "artifact_version": types.String(),
            "extension": self.extension,
            "path": types.String(),
        }


@weave_class(weave_type=ArtifactVersionFileType)
class ArtifactVersionFile(weave_file.File):
    def __init__(
        self,
        entity_name,
        project_name,
        artifact_name,
        artifact_version,
        path,
        extension=None,
    ):
        self.entity_name = entity_name
        self.project_name = project_name
        self.artifact_name = artifact_name
        self.artifact_version = artifact_version
        self.extension = extension
        self.path = path
        if self.extension is None:
            self.extension = weave_file.path_ext(path)

    @property
    def artifact(self):
        wb_artifact = wandb_api.wandb_public_api().artifact(
            "%s/%s/%s:%s"
            % (
                self.entity_name,
                self.project_name,
                self.artifact_name,
                self.artifact_version,
            )
        )
        return artifacts_local.WandbArtifact.from_wb_artifact(wb_artifact)

    def get_local_path(self):
        entry = (
            wandb_api.wandb_public_api()
            .artifact(
                "%s/%s/%s:%s"
                % (
                    self.entity_name,
                    self.project_name,
                    self.artifact_name,
                    self.artifact_version,
                )
            )
            .get_path(self.path)
        )
        return entry.download()

    def _contents(self):
        return open(self.get_local_path(), encoding="ISO-8859-1").read()


ArtifactVersionFileType.instance_class = ArtifactVersionFile
ArtifactVersionFileType.instance_classes = ArtifactVersionFile


class ArtifactVersionDirType(types.ObjectType):
    name = "artifactversion-dir"

    def __init__(self):
        pass

    def property_types(self):
        return {
            "fullPath": types.String(),
            "size": types.Int(),
            "dirs": types.Dict(
                types.String(), types.SubDirType(ArtifactVersionFileType())
            ),
            "files": types.Dict(types.String(), ArtifactVersionFileType()),
        }


@weave_class(weave_type=ArtifactVersionDirType)
class ArtifactVersionDir(weave_file.Dir):
    def _path_return_type(self, path):
        return path_type(os.path.join(self.fullPath, path))

    def _path(self, path):
        return open_(os.path.join(self.fullPath, path))


ArtifactVersionDirType.instance_classes = ArtifactVersionDir
ArtifactVersionDirType.instance_class = ArtifactVersionDir


def artifact_version_path(av: wandb_public.Artifact, path: str):
    av = av._saved_artifact
    manifest = av.manifest
    manifest_entry = manifest.get_entry_by_path(path)
    if manifest_entry is not None:
        # This is a file
        return ArtifactVersionFile(
            av.entity, av.project, av._sequence_name, av.version, path
        )
    # This is not a file, assume its a directory. If not, we'll return an empty result.
    cur_dir = path  # give better name so the rest of this code block is more readable
    if cur_dir == "":
        dir_ents = av.manifest.entries.values()
    else:
        dir_ents = av.manifest.get_entries_in_directory(cur_dir)
    sub_dirs: dict[str, weave_file.SubDir] = {}
    files = {}
    for entry in dir_ents:
        entry_path = entry.path
        rel_path = os.path.relpath(entry_path, path)
        rel_path_parts = rel_path.split("/")
        if len(rel_path_parts) == 1:
            # Its a file within cur_dir
            files[entry_path] = ArtifactVersionFile(
                av.entity,
                av.project,
                av._sequence_name,
                av.version,
                entry_path,
                extension=weave_file.path_ext(path),
            )
        else:
            dir_name = rel_path_parts[0]
            if dir_name not in sub_dirs:
                dir_ = weave_file.SubDir(entry_path, 1111, {}, {})
                sub_dirs[dir_name] = dir_
            dir_ = sub_dirs[dir_name]
            if len(rel_path_parts) == 2:
                dir_.files[rel_path_parts[1]] = ArtifactVersionFile(
                    av.entity,
                    av.project,
                    av._sequence_name,
                    av.version,
                    entry_path,
                    extension=weave_file.path_ext(entry_path),
                )
            else:
                dir_.dirs[rel_path_parts[1]] = 1
    return ArtifactVersionDir(path, 1591, sub_dirs, files)
