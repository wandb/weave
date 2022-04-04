# Very much WIP

import os
import json

import PIL
import PIL.Image
import numpy

from ..api import op, weave_class
from .. import weave_types as types
from ..ops_primitives import file
from . import ArtifactVersion

from .. import storage
from .. import tags
from .. import util


class AssetType(types.Type):
    name = "asset"


@weave_class(weave_type=AssetType)
class Asset(object):
    @op(
        name="asset-artifactVersion",
        input_type={"asset": types.Any()},
        # TODO: ArtifactVersion()
        # and return a FakeStorageArtifact ??
        output_type=ArtifactVersion(),
    )
    def artifactVersion(asset):
        from . import tags

        artifact = tags.get_tag(asset, "artifact")
        return artifact


class Image(Asset):
    def __init__(self, data, boxes=None):
        if isinstance(data, PIL.Image.Image):
            self._image = data
        elif isinstance(data, numpy.ndarray):
            self._image = PIL.Image.fromarray(data.astype(numpy.uint8), mode="L")
        else:
            raise Exception("invalid")
        self._boxes = boxes

    def add_box(self, box):
        if self._boxes is None:
            self._boxes = []
        self._boxes.add(box)

    def to_json(self, artifact):
        img_path = "image.png"
        with artifact.new_file(f"{img_path}", binary=True) as f:
            self._image.save(f, format="png")
        # Remember, artifact manifest forces us to wire pointers to other
        #     artifact files through so that the database can see them...
        return {
            # some of this is type information
            # some of this is file metadata
            # so do we need to allow to return arbitrary data here, or can
            # we say you're returning the filled in type, with a pointer to
            # the underlying data?
            # but the boxes themselves aren't part of the type...
            "type": "image_file",
            "format": "png",
            "path": img_path,
            "sha256": "asdfk",
            "size": 142,
            "boxes": self._boxes,
        }

    @classmethod
    def from_json(cls, obj, artifact):
        with artifact.open(obj["path"], binary=True) as f:
            image = PIL.Image.open(f, formats=("png",))
        result = cls(image, obj["boxes"])
        result.artifact = artifact
        return result


# TODO: the type is supposed to have a bunch of shit in it
#     the frontend uses the type for things like class colors


class WBImageType(types.ObjectType):
    name = "image_file"

    def property_types(self):
        return {
            "format": types.String(),
            "path": types.String(),
            "sha256": types.String(),
            "size": types.Int(),
            # TODO: either mark optional, or have a different version
            #     of this object when its actually saved
            # But doing this forces an artifact ref on all serialized WBImage
            #     objects. Even when being used inside of an artifact....
            # We really only want it when this is a ref for use outside
            #     the artifact.
            # 'artifact': artifacts.ArtifactType()
        }


@weave_class(weave_type=WBImageType)
class WBImage:
    @classmethod
    def from_numpy(cls, arr):
        image = PIL.Image.fromarray(arr.astype(numpy.uint8), mode="L")
        path = "/tmp/my-image.png"
        image.save(path, format="png")
        # We pass None for artifact here. But its not yet marked as optional
        # in the type
        return cls("png", path, "asdfk", 142)

    def __init__(self, format, path, sha256, size):
        self.format = format
        self.path = path
        self.sha256 = sha256
        self.size = size
        # self.artifact = artifact

    @op(
        name="wbImage-url",
        input_type={"image": WBImageType()},  # TODO requires Saved() mixin on type?
        output_type=types.String(),
    )
    def url(image):
        # artifact = tags.get_tag(image, "artifact")
        artifact = storage.get_ref(image).artifact
        # TODO: hack: hardcoding latest here, and an actual internal path
        # This is old code and should be updated
        res = "file://" + os.path.abspath(
            os.path.join("local-artifacts", artifact._name, "latest", image.path)
        )
        return res


WBImageType.instance_classes = WBImage
WBImageType.instance_class = WBImage


# TODO: this should actually be artifact file, not just file.
@op(name="file-media", input_type={"file": types.FileType()}, output_type=WBImageType())
def file_readwbimage(file):
    return file


@op(name="image-url", input_type={"image": WBImageType()}, output_type=types.String())
def image_url(image):
    artifact = image.artifact
    artifact_path = artifact.get_path(image.path)
    return artifact_path.uri()
