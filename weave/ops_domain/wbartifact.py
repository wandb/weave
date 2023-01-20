import os

from ..api import op, weave_class
from .. import weave_types as types
from . import file_wbartifact
from ..ops_primitives import file_local
from .. import ref_base
from .. import artifact_local
from .. import artifact_wandb
from ..ops_primitives import file as weave_file


class ArtifactVersionType(types._PlainStringNamedType):
    name = "artifactLocalVersion"
    instance_classes = artifact_wandb.WandbArtifact
    instance_class = artifact_wandb.WandbArtifact

    # TODO: what should these do?
    #   return an ArtifactRef
    def save_instance(self, obj, artifact, name):
        return artifact_wandb.WandbArtifactRef(obj, None)

    def load_instance(self, artifact, name, extra=None):
        return artifact


@weave_class(weave_type=ArtifactVersionType)
class ArtifactVersion:
    @op(
        name="artifactLocalVersion-fileReturnType",
        input_type={"artifactVersion": ArtifactVersionType(), "path": types.String()},
        output_type=types.TypeType(),
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

    @op(name="artifactLocalVersion-name")
    def name(artifactVersion: artifact_wandb.WandbArtifact) -> str:  # type: ignore
        # TODO: we actually get an artifact version file here because
        # we get refs types messed up somehow
        return getattr(artifactVersion, "name", "BUG a192bx (search weave code)")

    @op(
        name="artifactLocalVersion-file",
        input_type={"artifactVersion": ArtifactVersionType(), "path": types.String()},
        # TODO: This Type is not complete (missing DirType())
        # TODO: This needs to call ArtifactVersion.path_type()
        output_type=artifact_wandb.ArtifactVersionFileType(),
    )
    # TODO: This function should probably be called path, but it return Dir or File.
    # ok...
    def file(artifactVersion, path):
        if ":" in path:
            # This is a URI

            ref = ref_base.Ref.from_str(path)
            artifactVersion = ref.artifact
            path = ref.path

        self = artifactVersion
        # TODO: hideous type-switching here. Need to follow the
        # generic WeaveJS op pattern in list_.py

        if isinstance(self, artifact_local.LocalArtifact):
            return file_local.LocalFile(os.path.join(self._read_dirname, path))

        # rest of implementation if for WandbArtifact
        av = self._saved_artifact

        manifest = av.manifest
        manifest_entry = manifest.get_entry_by_path(path)
        if manifest_entry is not None:
            # This is a file
            return self.get_file(path)
        # This is not a file, assume its a directory. If not, we'll return an empty result.
        cur_dir = (
            path  # give better name so the rest of this code block is more readable
        )
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
                # TODO: I haven't tested this since changin ArtifactVersionFile implementation
                files[rel_path_parts[0]] = self.get_file(entry_path)
            else:
                dir_name = rel_path_parts[0]
                if dir_name not in sub_dirs:
                    dir_ = weave_file.SubDir(entry_path, 1111, {}, {})
                    sub_dirs[dir_name] = dir_
                dir_ = sub_dirs[dir_name]
                if len(rel_path_parts) == 2:
                    # TODO: I haven't tested this since changin ArtifactVersionFile implementation
                    dir_.files[rel_path_parts[1]] = self.get_file(entry_path)
                else:
                    dir_.dirs[rel_path_parts[1]] = 1
        if not sub_dirs and not files:
            return None
        return file_wbartifact.ArtifactVersionDir(path, 1591, sub_dirs, files)


@op(
    name="file-artifactVersion",
    input_type={
        "file": types.union(types.FileType(), artifact_wandb.ArtifactVersionFileType())
    },
    output_type=ArtifactVersionType(),
)
def artifactVersion(file):
    return file.artifact
