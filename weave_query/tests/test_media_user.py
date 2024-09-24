from PIL import Image

from weave.legacy.weave import api as weave
from weave.legacy.weave import context_state
from weave.legacy.weave.ops_primitives import geom as media_user


def test_im_with_metadata():
    base_im = Image.linear_gradient("L").resize((32, 32))
    ims = [
        media_user.ImageWithBoxes(
            base_im,
            [
                media_user.BoundingBox2D(
                    media_user.Point2D(1, 2), media_user.Size2D(5, 9)
                )
            ],
        ),
        media_user.ImageWithBoxes(
            base_im.rotate(4),
            [
                media_user.BoundingBox2D(
                    media_user.Point2D(5, 9), media_user.Size2D(1, 2)
                )
            ],
        ),
    ]
    ims_saved = weave.save(ims)
    assert (
        weave.use(
            ims_saved.map(
                lambda im: im.get_boxes().map(lambda box: box.center().get_x()).sum()
            ).sum()
        )
        == 9.0
    )
