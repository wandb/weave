from tempfile import NamedTemporaryFile

from weave.integrations.pil import get_pil_patcher


def test_patching_import_order():
    # This test verifies the correct behavior if patching occurs after the construction
    # of an image
    # With the refactored integration system, we use the patcher directly
    patcher = get_pil_patcher()
    
    # First ensure we start with a clean state
    if patcher._patched:
        patcher.undo_patch()
    
    assert not patcher._patched
    
    import PIL

    # Create an image before patching
    image = PIL.Image.new("RGB", (10, 10))
    with NamedTemporaryFile(suffix=".png") as f:
        image.save(f.name)
        image = PIL.Image.open(f.name)

    # Apply the patch after image creation
    patcher.attempt_patch()
    assert patcher._patched

    # This should work without issues even though the image was created before patching
    image.crop((0, 0, 10, 10))
    
    # Clean up: re-apply patch for other tests
    if not patcher._patched:
        patcher.attempt_patch()