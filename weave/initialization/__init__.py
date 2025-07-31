from .moviepy_video_thread_safety import apply_threadsafe_patch_to_moviepy_video
from .pil_image_thread_safety import apply_threadsafe_patch_to_pil_image

apply_threadsafe_patch_to_pil_image()
apply_threadsafe_patch_to_moviepy_video()

__all__: list[str] = []
