import os
import tempfile
import subprocess
from pathlib import Path

import pytest
from moviepy.editor import VideoClip, VideoFileClip, ColorClip

import weave

"""This module tests edge cases in the Video type handler."""


@pytest.fixture
def sample_mp4_path():
    """Create a sample MP4 file and return its path."""
    with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as tmp:
        tmp_path = tmp.name
    
    clip = ColorClip(size=(32, 32), color=(255, 0, 0), duration=0.5)
    clip.fps = 24
    clip.write_videofile(tmp_path, codec="libx264", audio=False, verbose=False, logger=None)
    
    return tmp_path


@pytest.fixture
def sample_gif_path():
    """Create a sample GIF file and return its path."""
    with tempfile.NamedTemporaryFile(suffix=".gif", delete=False) as tmp:
        tmp_path = tmp.name
    
    clip = ColorClip(size=(32, 32), color=(0, 255, 0), duration=0.5)
    clip.fps = 10
    clip.write_gif(tmp_path)
    
    return tmp_path


@pytest.fixture
def sample_webm_path():
    """Create a sample WEBM file and return its path."""
    with tempfile.NamedTemporaryFile(suffix=".webm", delete=False) as tmp:
        tmp_path = tmp.name
    
    clip = ColorClip(size=(32, 32), color=(0, 0, 255), duration=0.5)
    clip.fps = 24
    clip.write_videofile(tmp_path, codec="libvpx", audio=False, verbose=False, logger=None)
    
    return tmp_path


def test_load_without_filename_extension(client, sample_mp4_path):
    """Test loading a video from a file without extension and ensure format is detected."""
    # Copy file to a path without extension
    with tempfile.NamedTemporaryFile(delete=False) as tmp:
        tmp_path = tmp.name
    
    import shutil
    shutil.copyfile(sample_mp4_path, tmp_path)
    
    # Load the video without extension
    clip = VideoFileClip(tmp_path)
    
    # Try to publish it - this should use DEFAULT_VIDEO_FORMAT (gif)
    ref = weave.publish(clip)
    
    # Check that we can get it back
    recovered = weave.ref(ref.uri()).get()
    assert isinstance(recovered, VideoClip)
    
    # Clean up
    os.unlink(tmp_path)


def test_videoclip_with_no_format_attribute(client):
    """Test publishing a VideoClip with no format attribute."""
    class CustomVideoClip(VideoClip):
        def __init__(self):
            super().__init__()
            self.size = (64, 64)
            self.duration = 1.0
            self.fps = 24
            
        def make_frame(self, t):
            # Return a blank frame (required for VideoClip)
            import numpy as np
            return np.zeros((self.size[1], self.size[0], 3), dtype=np.uint8)
    
    clip = CustomVideoClip()
    # This should use the DEFAULT_VIDEO_FORMAT
    ref = weave.publish(clip)
    
    # Check we can get it back
    recovered = weave.ref(ref.uri()).get()
    assert isinstance(recovered, VideoClip)


def test_multiple_video_formats(client, sample_mp4_path, sample_gif_path, sample_webm_path):
    """Test that we can publish videos of different formats in the same session."""
    mp4_clip = VideoFileClip(sample_mp4_path)
    gif_clip = VideoFileClip(sample_gif_path)
    webm_clip = VideoFileClip(sample_webm_path)
    
    # Publish all three
    mp4_ref = weave.publish(mp4_clip)
    gif_ref = weave.publish(gif_clip)
    webm_ref = weave.publish(webm_clip)
    
    # Retrieve them all
    mp4_recovered = weave.ref(mp4_ref.uri()).get()
    gif_recovered = weave.ref(gif_ref.uri()).get()
    webm_recovered = weave.ref(webm_ref.uri()).get()
    
    # Check they're all valid
    assert isinstance(mp4_recovered, VideoClip)
    assert isinstance(gif_recovered, VideoClip)
    assert isinstance(webm_recovered, VideoClip)


@pytest.mark.skip("Runs as a subprocess - skipped in regular test runs")
def test_many_videos_will_consistently_log():
    """Test that we can save many videos without issues."""
    res = subprocess.run(
        ["python", "tests/trace/type_handlers/Video/video_saving_script.py"],
        capture_output=True,
        text=True,
    )
    
    # This should always be True because the future executor won't raise an exception
    assert res.returncode == 0
    
    # But if there's an issue, the stderr will contain `Task failed:`
    assert "Task failed" not in res.stderr