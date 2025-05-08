"""This script is intended to be part of a test in video_test.py.

Similar to image_saving_script.py, this tests that we can save a video multiple times
without issues. In case of failure, you'll see a `Task Failed: ...` message in stderr.
"""

from moviepy.editor import VideoFileClip

import weave


def run_vid_test():
    weave.init("test-project")
    video = VideoFileClip("tests/trace/type_handlers/Video/test_video.mp4")

    @weave.op
    def test():
        return video

    test()


if __name__ == "__main__":
    run_vid_test()
