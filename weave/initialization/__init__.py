import logging
import os

from .moviepy_video_thread_safety import apply_threadsafe_patch_to_moviepy_video
from .pil_image_thread_safety import apply_threadsafe_patch_to_pil_image

apply_threadsafe_patch_to_pil_image()
apply_threadsafe_patch_to_moviepy_video()

# Configure httpx logging if WEAVE_DEBUG_HTTP is enabled
if os.environ.get("WEAVE_DEBUG_HTTP") == "1":
    logging.getLogger("httpx").setLevel(logging.DEBUG)

__all__: list[str] = []
