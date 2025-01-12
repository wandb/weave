"""This script is intended to be part of a test in image_test.py.

In the failure case, you'll see a `Task Failed: ...` because PIL couldn't fully load the
image.  The exact failure seems to depend on the type of image, file size, etc, but it
always results in either an incomplete or no image getting uploaded.  Sometimes the errors
are blank assertions inside PIL itself, so it's hard to guard against them in the test.
Instead, we just check for `Task Failed: ...` in stderr."""

from PIL import Image

import weave


def run_img_test():
    weave.init("test-project")
    img = Image.open("trace/type_handlers/Image/cat.png")

    @weave.op
    def test():
        return img

    test()


if __name__ == "__main__":
    run_img_test()
