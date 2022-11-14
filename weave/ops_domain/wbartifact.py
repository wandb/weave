import os

from wandb.apis import public as wandb_api

from ..api import op, weave_class
from .. import weave_types as types
from . import file_wbartifact
from ..ops_primitives import file_local
from .. import artifacts_local
from .. import refs
from ..ops_primitives import file as weave_file
from ..ops_domain.wbmedia import ImageArtifactFileRef

class ArtifactVersionType(types._PlainStringNamedType):
    name = "artifactVersion"
    instance_classes = artifacts_local.WandbArtifact
    instance_class = artifacts_local.WandbArtifact

    # TODO: what should these do?
    #   return an ArtifactRef
    def save_instance(self, obj, artifact, name):
        return refs.WandbArtifactRef(obj, None)

    def load_instance(self, artifact, name, extra=None):
        return artifact


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
        output_type=refs.ArtifactVersionFileType(),
    )
    # TODO: This function should probably be called path, but it return Dir or File.
    # ok...
    def path(artifactVersion, path):
        if ":" in path:
            # This is a URI

            ref = refs.Ref.from_str(path)
            artifactVersion = ref.artifact
            path = ref.path

        self = artifactVersion
        # TODO: hideous type-switching here. Need to follow the
        # generic WeaveJS op pattern in list_.py

        if isinstance(self, artifacts_local.LocalArtifact):
            return file_local.LocalFile(os.path.join(self._read_dirname, path))

        # rest of implementation if for WandbArtifact
        av = self._saved_artifact

        manifest = av.manifest
        manifest_entry = manifest.get_entry_by_path(path)
        if manifest_entry is not None:
            # This is a file
            return file_wbartifact.ArtifactVersionFile(self, path)
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
                files[entry_path] = file_wbartifact.ArtifactVersionFile(
                    self,
                    entry_path,
                )
            else:
                dir_name = rel_path_parts[0]
                if dir_name not in sub_dirs:
                    dir_ = weave_file.SubDir(entry_path, 1111, {}, {})
                    sub_dirs[dir_name] = dir_
                dir_ = sub_dirs[dir_name]
                if len(rel_path_parts) == 2:
                    # TODO: I haven't tested this since changin ArtifactVersionFile implementation
                    dir_.files[rel_path_parts[1]] = file_wbartifact.ArtifactVersionFile(
                        self,
                        entry_path,
                    )
                else:
                    dir_.dirs[rel_path_parts[1]] = 1
        return file_wbartifact.ArtifactVersionDir(path, 1591, sub_dirs, files)


class ArtifactAssetType(types._PlainStringNamedType):
    name = "asset"

asset_type = types.union(
    ImageArtifactFileRef.WeaveType(),
    ArtifactAssetType()
)

@op(
    name="asset-artifactVersion",
    input_type={"asset": asset_type},
    output_type=ArtifactVersionType(),
)
def artifactVersion(asset):
    return asset.artifact
