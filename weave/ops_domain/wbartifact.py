import os

from wandb.apis import public as wandb_api

from ..api import op, weave_class
from .. import weave_types as types
from . import file_wbartifact
from ..ops_primitives import file_local
from .. import artifacts_local
from .. import refs
from ..ops_primitives import file as weave_file
from .. import panels
from .. import ops


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
        name="artifactVersion-manifestDiff",
        input_type={"self": ArtifactVersionType(), "other": ArtifactVersionType()},
        # output_type=types.TypedDict(
        #     {
        #         "a_only": types.List(types.String()),
        #         "b_only": types.List(types.String()),
        #         "modified": types.List(types.String()),
        #         "unchanged": types.List(types.String()),
        #     }
        # ),
        render_info={"type": "function"},
    )
    def diff(self, other) -> panels.Card:
        def stringify_artifact_manifest(manifest):
            return {name: obj.digest for name, obj in manifest.entries.items()}

        def _diff(a, b):
            a_only = set(a.keys()) - set(b.keys())
            b_only = set(b.keys()) - set(a.keys())
            unchanged = set()
            changed = set()

            intersection = set(a.keys()) & set(b.keys())
            for k in intersection:
                if a[k] == b[k]:
                    unchanged.add(k)
                else:
                    changed.add(k)

            return {
                "a_only": list(a_only),
                "b_only": list(b_only),
                "unchanged": list(unchanged),
                "changed": list(changed),
            }

        self_manifest = stringify_artifact_manifest(self.manifest)
        other_manifest = stringify_artifact_manifest(other.manifest)
        result = _diff(self_manifest, other_manifest)

        def template(text, color):
            return f"""<p style="color:{color}; font-family:'Source Sans Pro',sans-serif;">{text}</p>"""

        def first_artifact_html():
            a_only = [template(t, "red") for t in result["a_only"]]
            b_only = [template(t, "white") for t in result["b_only"]]
            unchanged = [template(t, "black") for t in result["unchanged"]]
            changed = [template(t, "orange") for t in result["changed"]]

            html = a_only + b_only + unchanged + changed
            html = "\n".join(html)

            return html

            # op = ops.Html(html)
            # return panels.Html(op)

        def second_artifact_html():
            a_only = [template(t, "white") for t in result["a_only"]]
            b_only = [template(t, "green") for t in result["b_only"]]
            unchanged = [template(t, "black") for t in result["unchanged"]]
            changed = [template(t, "orange") for t in result["changed"]]

            html = a_only + b_only + unchanged + changed
            html = "\n".join(html)

            return html

            # op = ops.Html(html)
            # return panels.Html(op)

        def artifact_html():

            first = first_artifact_html()
            second = second_artifact_html()
            html = f"""
            <html>
            <head>
                <title>Title of the document</title>
                <style>
                #boxes {{
                    content: "";
                    display: table;
                    clear: both;
                }}
                div {{
                    float: left;
                    width: 45%;
                    padding: 0 10px;
                }}
                #column1 {{
                    background-color: #FFF;
                }}
                #column2 {{
                    background-color: #FFF;
                }}
                h2 {{
                    color: #000000;
                    text-align: center;
                }}
                </style>
            </head>
            <body>
                <div id="column1">
                    <h2>First Artifact</h2>
                    {first}
                </div>
                <div id="column2">
                    <h2>Second Artifact</h2>
                    {second}
                </div>
            </body>
            </html>
            """

            return panels.Html(ops.Html(html))

        return panels.Card(
            title="ARTIFACT DIFF",
            subtitle="demo",
            content=[
                panels.CardTab(
                    name="HTML Diff",
                    content=panels.Group(
                        items=[
                            artifact_html()
                            # panels.LabeledItem(label="First Artifact", item=first_artifact_html()),
                            # panels.LabeledItem(label="Second Artifact", item=second_artifact_html()),
                        ],
                        prefer_horizontal=True,
                    ),
                ),
                panels.CardTab(
                    name="First Artifact Only",
                    content=panels.Group(items=result["a_only"]),
                ),
                panels.CardTab(
                    name="Second Artifact Only",
                    content=panels.Group(items=result["b_only"]),
                ),
                panels.CardTab(
                    name="Unchanged", content=panels.Group(items=result["unchanged"]),
                ),
                panels.CardTab(
                    name="Modified", content=panels.Group(items=result["changed"]),
                ),
            ],
        )

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
                    self, entry_path,
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
                        self, entry_path,
                    )
                else:
                    dir_.dirs[rel_path_parts[1]] = 1
        return file_wbartifact.ArtifactVersionDir(path, 1591, sub_dirs, files)


class ArtifactAssetType(types._PlainStringNamedType):
    name = "asset"


@op(
    name="asset-artifactVersion",
    input_type={"asset": ArtifactAssetType()},
    output_type=ArtifactVersionType(),
)
def artifactVersion(asset):
    return asset.artifact
