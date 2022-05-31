import pytest
import numpy as np
from PIL import Image
from .. import storage
from . import api as weave


def test_image():
    im = Image.linear_gradient("L").rotate(4)
    ref = storage.save(im)
    im2 = storage.get(ref)
    assert (np.array(im) == np.array(im2)).all()


def test_list_image_same_sizes():
    ims = [Image.linear_gradient("L").rotate(i * 4) for i in range(3)]
    ref = storage.save(ims)
    ims2 = storage.get(str(ref))
    assert len(ims) == len(ims2)
    for im, im2 in zip(ims, ims2):
        assert (np.array(im) == np.array(im2)).all()


def test_list_image_different_sizes_raises():
    ims = [
        Image.linear_gradient("L").resize((256 - i, 256)).rotate(i * 4)
        for i in range(3)
    ]
    with pytest.raises(weave.errors.WeaveSerializeError):
        ref = storage.save(ims)
