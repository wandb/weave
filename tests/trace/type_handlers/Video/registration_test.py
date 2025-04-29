from moviepy.editor import ColorClip, VideoFileClip

"""Test that the video type handler is properly registered."""


def test_videofileclip_is_detected():
    """Test that VideoFileClip is properly detected as a VideoClip."""
    # Import the video module to ensure it's registered
    from weave.type_handlers.Video.video import is_instance

    clip = ColorClip(size=(64, 64), color=(128, 0, 128), duration=1)
    clip.fps = 24

    # Create a temporary file
    import tempfile

    with tempfile.NamedTemporaryFile(suffix=".mp4") as tmp:
        clip.write_videofile(
            tmp.name, codec="libx264", audio=False, verbose=False, logger=None
        )
        file_clip = VideoFileClip(tmp.name)

        # Test the is_instance function directly
        assert is_instance(
            file_clip
        ), "VideoFileClip should be recognized by is_instance"
