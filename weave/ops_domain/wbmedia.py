# Implements backward compatibility for existing W&B Media types.

import dataclasses
import typing
from ..language_features.tagging.tag_store import isolated_tagging_context
from .. import types
from .. import errors
from .. import api as weave
from .. import artifact_fs
from ..ops_primitives import html
from ..ops_primitives import markdown
from functools import cached_property


@dataclasses.dataclass(frozen=True)
class LegacyImageArtifactFileRefType(types.ObjectType):
    name = "legacy-image-file"

    def property_types(self) -> dict[str, types.Type]:
        raise errors.WeaveTypeError(
            f"LegacyImageArtifactFileRefType should never be used! it is a temp type"
        )

    @classmethod
    def type_of_instance(cls, obj):
        raise errors.WeaveTypeError(
            f"LegacyImageArtifactFileRefType should never be used! it is a temp type"
        )

    def _to_dict(self) -> dict:
        raise errors.WeaveTypeError(
            f"LegacyImageArtifactFileRefType should never be used! it is a temp type"
        )

    @classmethod
    def from_dict(cls, d):
        raise errors.WeaveTypeError(
            f"LegacyImageArtifactFileRefType should never be used! it is a temp type"
        )


@dataclasses.dataclass(frozen=True)
class ImageArtifactFileRefType(types.ObjectType):
    """
    The ImageArtifactFileRefType type is fairly complicated because the type representation coming from
    the SDK does not conform to the expectations of the type system in Weave1. However, we want to operate
    on this type as if it is just an `ObjectType`. So there are a few workarounds here:
        1. The serialized format of the type is a dictionary with `boxLayers`, `boxScoreKeys`, `maskLayers`, and `classMap`.
           This representation does not look like a Weave1 type, so we must override the to/from dict methods. Doing this
           allows us to play nicely with Weave0 FE.
        2. To conform to the ObjectType expectations, the type vars (`boxes` and `masks`) must align with the data properties
           in the data object below (`ImageArtifactFileRef`). Basically, if it weren't for SDK Weave and Weave0, we could just
           ignore the underscore properties and this would all be a lot easier.
    Moreover, the two representations (non underscore and underscore properties) can be derived from each-other, so we use python
    properties to ensure they are only calculated once. (And a helper constructor `init_from_sdk_attributes` which can be used when
    initializing from SDK data).
    """

    name = "image-file"
    boxes: types.Type = types.TypedDict({})
    masks: types.Type = types.TypedDict({})

    _boxLayers: typing.Optional[dict[str, list]] = None
    _boxScoreKeys: typing.Optional[list] = None
    _maskLayers: typing.Optional[dict[str, list]] = None
    _classMap: typing.Optional[dict[int, str]] = None

    @classmethod
    def type_attrs(cls):
        return ["boxes", "masks"]

    @cached_property
    def boxLayers(self):
        if self._boxLayers is None:
            # TODO: Figure convert boxes to layers
            return {}

        return self._boxLayers

    @cached_property
    def boxScoreKeys(self):
        if self._boxScoreKeys is None:
            # TODO: Figure convert boxes to layers
            return []

        return self._boxScoreKeys

    @cached_property
    def maskLayers(self):
        if self._maskLayers is None:
            # TODO: Figure convert boxes to layers
            return {}

        return self._maskLayers

    @cached_property
    def classMap(self):
        if self._classMap is None:
            return {}
        return self._classMap

    @classmethod
    def init_from_sdk_attributes(
        cls: typing.Type["ImageArtifactFileRefType"],
        boxLayers: typing.Optional[dict[str, list]] = None,
        boxScoreKeys: typing.Optional[list] = None,
        maskLayers: typing.Optional[dict[str, list]] = None,
        classMap: typing.Optional[dict[int, str]] = None,
    ) -> "ImageArtifactFileRefType":
        _boxLayers = boxLayers or {}
        _boxScoreKeys = boxScoreKeys or []
        _maskLayers = maskLayers or {}
        _classMap = classMap or {}

        boxes_type = types.TypedDict(
            {
                box_key: types.optional(
                    types.List(
                        types.TypedDict(
                            {
                                "box_caption": types.optional(types.String()),
                                "class_id": types.Int(),
                                "domain": types.optional(types.String()),
                                "position": types.union(
                                    types.TypedDict(
                                        {
                                            "maxX": types.Int(),
                                            "maxY": types.Int(),
                                            "minX": types.Int(),
                                            "minY": types.Int(),
                                        }
                                    ),
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
                                    types.TypedDict(
                                        {
                                            "height": types.Int(),
                                            "middle": types.List(types.Int()),
                                            "width": types.Int(),
                                        }
                                    ),
                                ),
                                "scores": types.optional(
                                    types.TypedDict(
                                        {
                                            score_key: types.Float()
                                            for score_key in _boxScoreKeys
                                        }
                                    )
                                ),
                            }
                        )
                    )
                )
                for box_key in _boxLayers
            }
        )
        mask_type = types.TypedDict(
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
                for mask_key in _maskLayers
            }
        )

        res = cls(
            boxes_type, mask_type, _boxLayers, _boxScoreKeys, _maskLayers, _classMap
        )

        # res._boxLayers = _boxLayers or {}  # type: ignore
        # res._boxScoreKeys = _boxScoreKeys or []  # type: ignore
        # res._maskLayers = _maskLayers or {}  # type: ignore
        # res._classMap = _classMap or {}  # type: ignore

        return res

    def __eq__(self, other):
        # this custom __eq__ is needed because we need to allow
        # the lists to be in any order. This is only implemented
        # for the purpose of testing.

        if not isinstance(other, ImageArtifactFileRefType):
            return False
        boxLayerKeys = set(self.boxLayers.keys())
        otherBoxLayerKeys = set(other.boxLayers.keys())
        if boxLayerKeys != otherBoxLayerKeys:
            return False

        maskLayerKeys = set(self.maskLayers.keys())
        otherMaskLayerKeys = set(other.maskLayers.keys())
        if maskLayerKeys != otherMaskLayerKeys:
            return False

        boxScoreKeysSet = set(self.boxScoreKeys)
        otherBoxScoreKeysSet = set(other.boxScoreKeys)
        if boxScoreKeysSet != otherBoxScoreKeysSet:
            return False

        for key in boxLayerKeys:
            if set(self.boxLayers[key]) != set(other.boxLayers[key]):
                return False

        for key in maskLayerKeys:
            if set(self.maskLayers[key]) != set(other.maskLayers[key]):
                return False

        return self.classMap == other.classMap

    def property_types(self) -> dict[str, types.Type]:
        res = {
            "artifact": artifact_fs.FilesystemArtifactType(),
            "path": types.String(),
            "format": types.String(),
            "height": types.Int(),
            "width": types.Int(),
            "sha256": types.String(),
            "boxes": self.boxes,
            "masks": self.masks,
        }
        return res

    @classmethod
    def type_of_instance(cls, obj):
        # cls(
        #     types.TypeRegistry.type_of(obj.boxes),
        #     types.TypeRegistry.type_of(obj.masks),
        # )
        boxLayers = {
            key: [row["class_id"] for row in value] for key, value in obj.boxes.items()
        }
        boxScoreKeysSet = set()
        for boxLayer in boxLayers:
            for box in obj.boxes[boxLayer]:
                if box["scores"] is not None:
                    boxScoreKeysSet.update(list(box["scores"].keys()))
        boxScoreKeys = list(boxScoreKeysSet)

        maskLayers = {
            # Empty array here. We really should read in the mask data, then
            # find all the unique values. but that is really costly and is not
            # worth it. This is because `type_of_instance` is only called when
            # we are trying to re-serialize for transmission back to the client.
            # In these cases, having the correct classes in each key is not
            # needed.
            key: []
            for key in obj.masks.keys()
        }
        return cls.init_from_sdk_attributes(
            boxLayers=boxLayers, boxScoreKeys=boxScoreKeys, maskLayers=maskLayers
        )

    def _to_dict(self) -> dict:
        d: dict = {"_is_object": True}
        d = self.class_to_dict()
        d["_is_object"] = True
        d["boxLayers"] = self.boxLayers
        d["boxScoreKeys"] = self.boxScoreKeys
        d["maskLayers"] = self.maskLayers
        d["classMap"] = self.classMap
        return d

    @classmethod
    def from_dict(cls, d):
        return cls.init_from_sdk_attributes(
            d.get("boxLayers"),
            d.get("boxScoreKeys"),
            d.get("maskLayers"),
            d.get("classMap"),
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
    boxes: dict[str, list[dict]] = dataclasses.field(default_factory=dict)
    masks: dict[str, dict[str, str]] = dataclasses.field(default_factory=dict)
    classes: typing.Optional[dict] = None

    def __post_init__(self):
        # Here, we ensure the correct types for the boxes and masks this is
        # needed because the union branch of `recursively_build_pyarrow_array`
        # requires exact type matching!

        for box_set_id in self.boxes:
            box_set = self.boxes[box_set_id]
            for box in box_set:
                if "scores" in box:
                    if box["scores"] is not None:
                        # Scores are always floats
                        box["scores"] = {k: float(v) for k, v in box["scores"].items()}
                if "domain" in box and box["domain"] == "pixel":
                    py_number_type = int
                else:
                    py_number_type = float

                # Position values are either float or int based on the domain
                # spec
                box["position"] = {
                    k: py_number_type(v)
                    if k != "middle"
                    else [py_number_type(v[0]), py_number_type(v[1])]
                    for k, v in box["position"].items()
                }


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
class LegacyTableNDArrayType(types.Type):
    name = "ndarray"


# This shows a pattern for how to convert an in memory object (Html)
# to a W&B media type style FileRef, so that the existing frontend
# code can work with it.
@weave.op()
def html_file(html: html.Html) -> HtmlArtifactFileRef:
    from weave import storage

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
    from weave import storage

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
