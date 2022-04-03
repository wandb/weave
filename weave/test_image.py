from hashlib import sha256
import numpy as np
import os

from .ops_domain import image
from . import weave_types as types
from . import storage
from . import api
from .ops_primitives import artifacts
from . import tags


def test_save():
    im = image.WBImage.from_numpy(np.ones((5, 5)))
    ref = storage.save(im)
    im2 = ref.get()
    assert im.format == im2.format
    assert im.path == im2.path
    assert im.sha256 == im2.sha256
    assert im.size == im2.size


def test_to_python():
    im = image.WBImage.from_numpy(np.ones((5, 5)))
    obj_type = types.TypeRegistry.type_of(im)
    py_obj = storage.to_python(im)
    im2 = storage.from_python(py_obj)
    assert im.format == im2.format
    assert im.path == im2.path
    assert im.sha256 == im2.sha256
    assert im.size == im2.size


def test_local_artifact_ops():
    im = image.WBImage.from_numpy(np.ones((5, 5)))
    ref = storage.save(im)

    la = artifacts.LocalArtifact(ref.artifact._name, ref.artifact.version)
    im2_node = la.get("_obj")
    im2 = api.use(im2_node)

    # TODO: should we really allow users to get tags this way?
    #    that means we have to send them all out of the server.
    # Probably better to disallow as in Weave JS
    ref = storage.get_ref(im2)
    artifact = ref.artifact
    # artifact = tags.get_tag(im2, "artifact")
    assert artifact is not None

    url_node = im2.url()
    url = api.use(url_node)
    without_prefix = url[len("file://") :]

    assert os.path.exists(without_prefix)

    # Next: we need to serialize & deserialize tags!


# def test_image_data_url():
#     im = image.WBImage.from_numpy(np.ones((5, 5)))
#     url_node = ops.image_url(im)
#     url = api.use(url_node)
#     print('URL', url)
#     assert 1 == 2

# def test_readwbimage_op():
#     im = image.WBImage.from_numpy(np.ones((5, 5)))
#     ref = storage.save(im)

#     # Note this isn't the real API a user would, since they have ref
#     image_node = ops.local_artifact('local-artifacts/my-image').file('_obj.wbimage.json').image()

#     # the server would convert objects to dicts
#     # the client would convert these dicts back to objects

#     # Note: our world would be much better if the client asked for image.as_dict() instead
#     # of image directly, expecting a dict
#     # But, for now, just send the dict back, why not?

#     # TODO: write down various serialization cases (what case and what do we want?)
#     im2 = api.use(image_node)

#     # TODO save and read back a wbimage with the op
#     image_node = ops.file_readwbimage(ops.file_open('local-artifacts/my-image/_obj.wbimage.json'))
#     image = api.use(image_node)
#     # TODO: execute the same op as if we were javascript
#     #    we should get back the dict representation of the object
#     #    instead of a pointer to it
#     # Actually we can always return the typeddict instead of a ref for now
#     #    in save_instance on ObjectType
#     #    But can we demap that object back into an object?


# serializing objects for js
# when serializing results to a python requester
