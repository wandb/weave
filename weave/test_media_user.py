import numpy as np

from . import storage
from . import media_user


def test_im_with_metadata():
    box1 = media_user.Box(0, 0, 25, 40)
    box2 = media_user.Box(-5, -10, 100, 99)
    im = media_user.Image(media_user.CHANNEL_MODE_GRAYSCALE, np.ones((50, 50)))
    im_with_metadata = media_user.ImageWithMetadata(im)
    im_with_metadata.add_box(box1)
    im_with_metadata.add_box(box2)
    # TODO: This doesn't work right now...
    # arr = [im_with_metadata]
    arr = [{"image": im_with_metadata}]
    ref = storage.save(arr)
    arr2 = ref.get()

    assert arr2[0]["image"].boxes[0].l == arr[0]["image"].boxes[0].l
    assert arr2[0]["image"].boxes[0].t == arr[0]["image"].boxes[0].t
    assert arr2[0]["image"].boxes[0].w == arr[0]["image"].boxes[0].w
    assert arr2[0]["image"].boxes[0].h == arr[0]["image"].boxes[0].h

    assert (arr2[0]["image"].image.data == arr[0]["image"].image.data).all()
