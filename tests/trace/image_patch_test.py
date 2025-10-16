import os
from tempfile import NamedTemporaryFile

from weave.initialization import pil_image_thread_safety


def test_patching_import_order():
    # This test verifies the correct behavior if patching occurs after the construction
    # of an image
    assert pil_image_thread_safety._patched
    pil_image_thread_safety.undo_threadsafe_patch_to_pil_image()
    assert not pil_image_thread_safety._patched
    import PIL

    image = PIL.Image.new("RGB", (10, 10))
    # On Windows, we need delete=False to allow PIL to open the file
    with NamedTemporaryFile(suffix=".png", delete=False) as f:
        temp_path = f.name
        image.save(f.name)

    try:
        image = PIL.Image.open(temp_path)
        pil_image_thread_safety.apply_threadsafe_patch_to_pil_image()
        assert pil_image_thread_safety._patched
        image.crop((0, 0, 10, 10))
    finally:
        try:
            os.unlink(temp_path)
        except (OSError, PermissionError):
            pass
