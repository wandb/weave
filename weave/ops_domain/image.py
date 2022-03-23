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


# todo opAssetArtifactVersion, we can make this inherit from Asset
#    and implement it there.
# This object would need to save the av as in attribute
#
# But image should also have a .image_file() op that it can call.


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

    type_vars = {}

    def __init__(self):
        pass

    def property_types(self):
        return {
            "format": types.String(),
            "path": types.String(),
            "sha256": types.String(),
            "size": types.Number(),
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
        artifact = storage.get_ref(image).uri.artifact
        # TODO: hack: hardcoding latest here, and an actual internal path
        # This is old code and should be updated
        res = "file://" + os.path.abspath(
            os.path.join("local-artifacts", artifact._name, "latest", image.path)
        )
        return res

    def save_to_artifact(self, artifact):
        # Ew, this is how we check if we're in an artifact. We shouldn't
        # need to do this here.
        # TODO: the system should handle
        ref = storage.get_ref(self)
        artifact_path = f"image-{util.rand_string_n(8)}.png"
        if ref is not None:
            in_artifact = ref.uri.artifact
            artifact_path = self.path
            with in_artifact.open(self.path, binary=True) as f:
                contents = f.read()
        else:
            contents = open(self.path, "rb").read()
        artifact_tag = tags.get_tag(self, "artifact")
        if artifact_tag:
            return
        with artifact.new_file(artifact_path, binary=True) as f:
            f.write(contents)
        self.path = artifact_path


WBImageType.instance_classes = WBImage
WBImageType.instance_class = WBImage

# def to_json(self):
#     return {'type': 'image-file'}
# @classmethod
# def obj_repr(self, storage_obj):
#     return json.load(storage_obj.text_file)

# def to_json(self):
#     return {'type': 'image-file'}
# @classmethod
# def obj_repr(self, storage_obj):
#     return json.load(storage_obj.text_file)

# @classmethod
# def save_instance(cls, obj, artifact, name):
#     with artifact.new_file(f'{name}.wbimage.json') as f:
#         json.dump(obj.to_json(artifact), f)
#     return cls.type_of_instance(obj)

# @classmethod
# def load_instance(cls, artifact, name):
#     with artifact.open(f'{name}.wbimage.json') as f:
#         obj = json.load(f)
#     return Image.from_json(obj, artifact)


# TODO: this should actually be artifact file, not just file.
@op(name="file-media", input_type={"file": types.FileType()}, output_type=WBImageType())
def file_readwbimage(file):
    return file
    local_path = file.get_local_path()
    loaded = json.loads(open(local_path).read())
    print("LOADED", loaded)

    # Huge hack to get artifact path from artifact file
    artifact_path = os.path.dirname(local_path)
    artifact_path = "/".join(artifact_path.split("/")[1:])
    print("AP", artifact_path)

    # TODO: these are prob wrong
    artifact = storage.LocalArtifact(artifact_path)
    # return loaded
    im = Image.from_json(loaded, artifact)
    print("IM", im)
    return im


@op(name="image-url", input_type={"image": WBImageType()}, output_type=types.String())
def image_url(image):
    artifact = image.artifact
    artifact_path = artifact.get_path(image.path)
    return artifact_path.uri()


# So what do we need here...
#
# Should return a WBImage object.
#   this object should contain a reference to the storage its contained in
# Returned objects need to be serializable
#
# we make opAssetArtifact version return the Storage() object
# And then file() gets a file from that object.

# OK so type.save() should return whatever's important object the object
#       type.load() should take that and return the object
# So I need to change how save works, currently it forces you into a specific
#    pattern

# So it seems like objects need two things:
#   convert to pure python structure (to_json/from_json)
#   make pointer to any object
# But for example making image a pure python structure requires it to be able
#   to make a pointer to the underlying image.
# And the resulting structure can only be used for recovering the actual object
#   if we have access to the original storage for the object.

# OK so... keep something like the current media interface
# to_json() returns a serializable version of yourself, from_json the opposite
#     you have access to storage, an Artifact like object you can write to.
# Doing weave.use(<someObj>) gives you actual Class
#     but in the browser you get the serialized version of the object
# You can do save() on any object which will save it to an artifact, or
#     save a new version of the artifact its in (if its a top-level object)
# If not a top-level object, what do we do?
#
# For local data browsing, we save to a local file interface that is like
# an Artifact. We can also implement the Artifact interface on top of HDF5
#    and other systems.
#
# There is a different between sending the result of to_json over the wire
#    and saving an object completely.
# We'll see where the rubber meets the road with this tmw

# OK doing use() always gets you the object in Python, but the to_json()
#    flavor in the browser.
# That doesn't stop us from saving the to_json representation inside an artifact.
# So after an op, we want to to_json the results
#    then save the to_json in the same artifact, then return the to_json
#        do we augment the to_json with the artifact_id then? Maybe...
#    Do it to see what needs to happen
#    Yeah it seems like we'll need to inject the storage to json in the object
#        so we can pass it between steps and recover it. (just like a ref
#        now includes storage ID)
#
# OK to_json needs to return a recoverable version of the object.
#   But the object is not recoverable if the json encoded value doesn't include
#      the storage location for sub objects


# TODO:
#   its kind of working..... so do a print in PanelImage to see what was fetched
#   and implement the rest of the ops the client sends to Weave
