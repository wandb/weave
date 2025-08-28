from tempfile import NamedTemporaryFile

from weave.initialization import pil_image_thread_safety
from weave.integrations.pil import get_pil_patcher


def test_patching_import_order():
    # This test verifies the correct behavior if patching occurs after the construction
    # of an image
    # Note: With the refactored integration system, we check the patcher state directly
    patcher = get_pil_patcher()
    
    # The patcher should already be patched from initialization
    assert patcher._patched
    
    # Undo the patch
    pil_image_thread_safety.undo_threadsafe_patch_to_pil_image()
    assert not patcher._patched
    
    import PIL

    image = PIL.Image.new("RGB", (10, 10))
    with NamedTemporaryFile(suffix=".png") as f:
        image.save(f.name)
        image = PIL.Image.open(f.name)

    # Re-apply the patch
    pil_image_thread_safety.apply_threadsafe_patch_to_pil_image()
    assert patcher._patched

    # This should work without issues
    image.crop((0, 0, 10, 10))
