# Implements backward compatibility for existing W&B Media types.

import dataclasses
import json
import typing

from weave_query import api as weave
from weave_query import artifact_fs, engine_trace, errors, file_base, types
from weave_query.language_features.tagging.tag_store import isolated_tagging_context
from weave_query.ops_primitives import html, markdown


class LegacyImageArtifactFileRef:
    # Dummy class to make LegacyImageArtifactFileRefType not have
    # pydantic.BaseModel as an instance class, which messes up type_of.
    pass


@dataclasses.dataclass(frozen=True)
class LegacyImageArtifactFileRefType(types.ObjectType):
    name = "legacy-image-file"

    instance_classes = LegacyImageArtifactFileRef  # type: ignore

    def property_types(self) -> dict[str, types.Type]:
        raise errors.WeaveTypeError(
            "LegacyImageArtifactFileRefType should never be used! it is a temp type"
        )

    @classmethod
    def type_of_instance(cls, obj):
        raise errors.WeaveTypeError(
            "LegacyImageArtifactFileRefType should never be used! it is a temp type"
        )

    def _to_dict(self) -> dict:
        raise errors.WeaveTypeError(
            "LegacyImageArtifactFileRefType should never be used! it is a temp type"
        )

    @classmethod
    def from_dict(cls, d):
        raise errors.WeaveTypeError(
            "LegacyImageArtifactFileRefType should never be used! it is a temp type"
        )


@dataclasses.dataclass(frozen=True)
class ImageArtifactFileRefType(types.ObjectType):
    name = "image-file"
    boxLayers: typing.Union[types.Type, dict] = types.TypedDict({})
    boxScoreKeys: typing.Union[types.Type, list] = types.List(types.UnknownType())
    maskLayers: typing.Union[types.Type, dict] = types.TypedDict({})
    classMap: typing.Union[types.Type, dict] = types.TypedDict({})

    # TODO: This should probably be standard for Type!
    def __post_init__(self):
        for type_attr in self.type_attrs():
            self.__dict__[type_attr] = types.parse_constliteral_type(
                self.__dict__[type_attr]
            )

    def _to_dict(self) -> dict:
        d: dict = {"_is_object": True}
        d = self.class_to_dict()
        d["_is_object"] = True
        d["boxLayers"] = types.constliteral_type_to_json(self.boxLayers)  # type: ignore
        d["boxScoreKeys"] = types.constliteral_type_to_json(self.boxScoreKeys)  # type: ignore
        d["maskLayers"] = types.constliteral_type_to_json(self.maskLayers)  # type: ignore
        d["classMap"] = types.constliteral_type_to_json(self.classMap)  # type: ignore
        return d

    # TODO: This should probably be standard for Type!
    @classmethod
    def from_dict(cls, d):
        return cls(
            d.get("boxLayers", {}),
            d.get("boxScoreKeys", []),
            d.get("maskLayers", {}),
            d.get("classMap", {}),
        )

    def property_types(self) -> dict[str, types.Type]:
        boxLayers = types.constliteral_type_to_json(self.boxLayers)  # type: ignore
        boxScoreKeys = types.constliteral_type_to_json(self.boxScoreKeys)  # type: ignore
        maskLayers = types.constliteral_type_to_json(self.maskLayers)  #   type: ignore
        res = {
            "artifact": artifact_fs.FilesystemArtifactType(),
            "path": types.String(),
            "format": types.String(),
            "height": types.Int(),
            "width": types.Int(),
            "sha256": types.String(),
            "boxes": types.optional(
                types.TypedDict(
                    {
                        box_key: types.optional(
                            types.List(
                                types.TypedDict(
                                    {
                                        "box_caption": types.optional(types.String()),
                                        "class_id": types.Int(),
                                        "domain": types.optional(types.String()),
                                        # The framework should do this merge types for us. But for
                                        # now we have to do it manually.
                                        "position": types.merge_types(
                                            types.TypedDict(
                                                {
                                                    "maxX": types.Float(),
                                                    "maxY": types.Float(),
                                                    "minX": types.Float(),
                                                    "minY": types.Float(),
                                                }
                                            ),
                                            types.TypedDict(
                                                {
                                                    "height": types.Float(),
                                                    "middle": types.List(types.Float()),
                                                    "width": types.Float(),
                                                }
                                            ),
                                        ),
                                        "scores": types.optional(
                                            types.TypedDict(
                                                {
                                                    score_key: types.optional(
                                                        types.Float()
                                                    )
                                                    for score_key in boxScoreKeys
                                                }
                                            )
                                        ),
                                    }
                                )
                            )
                        )
                        for box_key in boxLayers.keys()
                    }
                )
            ),
            "masks": types.optional(
                types.TypedDict(
                    {
                        mask_key: types.optional(
                            types.TypedDict(
                                {
                                    "_type": types.String(),
                                    "path": types.String(),
                                    "sha256": types.optional(types.String()),
                                }
                            )
                        )
                        for mask_key in maskLayers.keys()
                    }
                )
            ),
            "caption": types.optional(types.String()),
        }
        return res

    @classmethod
    def type_of_instance(cls, obj):
        if obj.boxes:
            boxLayers = {
                key: [row["class_id"] for row in value]
                for key, value in obj.boxes.items()
                if value is not None
            }
        else:
            boxLayers = {}
        boxScoreKeysSet = {}
        for boxLayer in boxLayers:
            for box in obj.boxes[boxLayer]:
                if box["scores"] is not None:
                    boxScoreKeysSet.update(dict.fromkeys(box["scores"].keys()))
        boxScoreKeys = list(boxScoreKeysSet)

        if obj.masks:
            maskLayers = {
                # Empty array here. We really should read in the mask data, then
                # find all the unique values. but that is really costly and is not
                # worth it. This is because `type_of_instance` is only called when
                # we are trying to re-serialize for transmission back to the client.
                # In these cases, having the correct classes in each key is not
                # needed.
                key: []
                for key in obj.masks.keys()
                if obj.masks[key] is not None
            }
        else:
            maskLayers = {}
        return cls(
            boxLayers=boxLayers,
            boxScoreKeys=boxScoreKeys,
            maskLayers=maskLayers,
            classMap={},
        )


@weave.weave_class(weave_type=ImageArtifactFileRefType)
@dataclasses.dataclass
class ImageArtifactFileRef:
    artifact: artifact_fs.FilesystemArtifact
    path: str
    format: str
    height: int
    width: int
    sha256: str
    boxes: typing.Optional[dict[str, list[dict]]] = dataclasses.field(
        default_factory=dict
    )  # type: ignore
    masks: typing.Optional[dict[str, dict[str, str]]] = dataclasses.field(
        default_factory=dict
    )  # type: ignore
    classes: typing.Optional[typing.Optional[dict]] = None
    caption: typing.Optional[str] = None


ImageArtifactFileRef.WeaveType = ImageArtifactFileRefType  # type: ignore
ImageArtifactFileRefType.instance_class = ImageArtifactFileRef
ImageArtifactFileRefType.instance_classes = ImageArtifactFileRef


@weave.type(__override_name="audio-file")  # type: ignore
class AudioArtifactFileRef:
    artifact: artifact_fs.FilesystemArtifact
    path: str
    sha256: str


@weave.type(__override_name="bokeh-file")  # type: ignore
class BokehArtifactFileRef:
    artifact: artifact_fs.FilesystemArtifact
    path: str
    sha256: str


@weave.type(__override_name="video-file")  # type: ignore
class VideoArtifactFileRef:
    artifact: artifact_fs.FilesystemArtifact
    path: str
    sha256: str


@weave.type(__override_name="object3D-file")  # type: ignore
class Object3DArtifactFileRef:
    artifact: artifact_fs.FilesystemArtifact
    path: str
    sha256: str


@weave.type(__override_name="molecule-file")  # type: ignore
class MoleculeArtifactFileRef:
    artifact: artifact_fs.FilesystemArtifact
    path: str
    sha256: str


@weave.type(__override_name="html-file")  # type: ignore
class HtmlArtifactFileRef:
    artifact: artifact_fs.FilesystemArtifact
    path: str
    sha256: str


# When a WB table is written to disk, it accumulates all the NDArrays into a
# single file so that these columns can be stored more efficiently. In the UI,
# we completely ignore such columns. The underlying data is even Nulled out!
#  With Weave1, we actually have the possibility of doing something with them if
# we wanted to! There are additional properties which we could use to add value:
# {"params": {"serialization_path": {"key": "output", "path":
# "media/serialized_data/498587e8.npz"}, "shape": [10]} However, I suspect we
# will just use the newer Weave1 NDArray type instead.


# 3/22/23: However as of this comment, we just return NoneType() instead of this
# type when we encounter legacy ndarray, since the table data is None
class LegacyTableNDArrayType(types.Type):
    name = "ndarray"


# This shows a pattern for how to convert an in memory object (Html)
# to a W&B media type style FileRef, so that the existing frontend
# code can work with it.
@weave.op()
def html_file(html: html.Html) -> HtmlArtifactFileRef:
    from weave_query import storage

    # This is a ref to the html object
    with isolated_tagging_context():
        ref = storage.save(html)
    path = ref.path
    if path is None:
        raise errors.WeaveInternalError("storage save returned None path")
    file_path = path + ".html"
    return HtmlArtifactFileRef(ref.artifact, file_path, file_path)


# Yet another pattern for returning a file inside an artifact!
# In this case, the WeaveJS Markdown panel expects a 'file' type
# (with extension in the type).
# TODO: merge all these patterns!!!!
@weave.op(
    output_type=artifact_fs.FilesystemArtifactFileType(
        weave.types.Const(weave.types.String(), "md")  # type: ignore
    )
)
def markdown_file(md: markdown.Markdown):
    from weave_query import storage

    with isolated_tagging_context():
        ref = storage.save(md)
    path = ref.path
    if path is None:
        raise errors.WeaveInternalError("storage save returned None path")
    return artifact_fs.FilesystemArtifactFile(ref.artifact, path + ".md")


ArtifactAssetType = types.union(
    ImageArtifactFileRef.WeaveType(),  # type: ignore
    AudioArtifactFileRef.WeaveType(),  # type: ignore
    BokehArtifactFileRef.WeaveType(),  # type: ignore
    VideoArtifactFileRef.WeaveType(),  # type: ignore
    Object3DArtifactFileRef.WeaveType(),  # type: ignore
    MoleculeArtifactFileRef.WeaveType(),  # type: ignore
    HtmlArtifactFileRef.WeaveType(),  # type: ignore
)


@weave.op(
    name="asset-artifactVersion",
    input_type={"asset": ArtifactAssetType},
    output_type=artifact_fs.FilesystemArtifactType(),
)
def artifactVersion(asset):
    return asset.artifact


@weave.op(
    name="asset-file",
    input_type={"asset": ArtifactAssetType},
    output_type=artifact_fs.FilesystemArtifactFileType(),
)
def asset_file(asset):
    return asset.artifact.path_info(asset.path)


@weave.op(
    name="file-media", output_type=lambda input_types: input_types["file"].wbObjectType
)
def file_media(file: artifact_fs.FilesystemArtifactFile):
    if isinstance(file, artifact_fs.FilesystemArtifactDir):
        raise errors.WeaveInternalError("File is None or a directory")
    tracer = engine_trace.tracer()
    with file.open() as f:
        with tracer.trace("file_media:jsonload"):
            data = json.load(f)
    if "path" not in data or data["path"] is None:
        raise errors.WeaveInternalError("Media File is missing path")
    file_path = data["path"]
    if file.path.endswith(".image-file.json"):
        res = ImageArtifactFileRef(
            artifact=file.artifact,
            path=file_path,
            format=data["format"],
            height=data.get("height", 0),
            width=data.get("width", 0),
            sha256=data.get("sha256", file_path),
            caption=data.get("caption", None),
        )
    elif any(
        file.path.endswith(path_suffix)
        for path_suffix in [
            ".audio-file.json",
            ".bokeh-file.json",
            ".video-file.json",
            ".object3D-file.json",
            ".molecule-file.json",
            ".html-file.json",
        ]
    ):
        type_cls, _ = file_base.wb_object_type_from_path(file.path)
        if type_cls.instance_class is None:
            raise errors.WeaveInternalError(
                f"op file-media: Media Type has not bound instance_class: {file.path}: {type_cls}"
            )
        res = type_cls.instance_class(
            file.artifact, file_path, data.get("sha256", file_path)
        )
    else:
        raise errors.WeaveInternalError(
            f"op file-media: Unknown media file type: {file.path}"
        )
    return res
