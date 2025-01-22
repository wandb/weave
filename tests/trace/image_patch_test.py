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
    with NamedTemporaryFile(suffix=".png") as f:
        image.save(f.name)
        image = PIL.Image.open(f.name)

    pil_image_thread_safety.apply_threadsafe_patch_to_pil_image()
    assert pil_image_thread_safety._patched

    image.crop((0, 0, 10, 10))
