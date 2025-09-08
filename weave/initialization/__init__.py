from .moviepy_video_thread_safety import install_moviepy_import_hook
from .pil_image_thread_safety import apply_threadsafe_patch_to_pil_image

apply_threadsafe_patch_to_pil_image()
install_moviepy_import_hook()

__all__: list[str] = []
