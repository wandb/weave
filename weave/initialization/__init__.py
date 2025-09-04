from .moviepy_video_thread_safety import (
    apply_threadsafe_patch_to_moviepy_video,  # For backward compatibility
    register_moviepy_import_hook,
)
from .pil_image_thread_safety import (
    apply_threadsafe_patch_to_pil_image,  # For backward compatibility
    register_pil_import_hook,
)

# Use deferred patching to improve startup performance
# These hooks will only apply patches when the respective libraries are actually imported
register_pil_import_hook()
register_moviepy_import_hook()

__all__: list[str] = []
