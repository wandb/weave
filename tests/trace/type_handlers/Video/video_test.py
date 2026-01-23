import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
from moviepy.editor import ColorClip, VideoClip, VideoFileClip

import weave
from weave.trace.weave_client import WeaveClient
from weave.type_handlers.Video.video import VideoFormat, write_video

"""When testing types, it is important to test:
Objects:
1. Publishing Directly
2. Publishing as a property
3. Using as a cell in a table

Calls:
4. Using as inputs, output, and output component (raw)
5. Using as inputs, output, and output component (refs)
"""


@pytest.fixture
def test_video() -> VideoClip:
    clip = ColorClip(size=(64, 64), color=(128, 0, 128), duration=1)
    clip.fps = 24
    return clip


def test_save_mp4_clip(tmp_path: Path, test_video: VideoClip):
    fp = str(tmp_path / "test.mp4")
    write_video(fp, test_video)
    # Check if the file was created
    assert os.path.exists(fp)
    # Check if the video was written
    assert os.path.getsize(fp) > 0


def test_save_webm_clip(tmp_path: Path, test_video: VideoClip):
    fp = str(tmp_path / "test.webm")
    write_video(fp, test_video)
    # Check if the file was created
    assert os.path.exists(fp)
    # Check if the video was written
    assert os.path.getsize(fp) > 0


def test_save_gif_clip(tmp_path: Path, test_video: VideoClip):
    fp = str(tmp_path / "test.gif")
    write_video(fp, test_video)
    # Check if the file was created
    assert os.path.exists(fp)
    # Check if the video was written
    assert os.path.getsize(fp) > 0


def test_save_no_ext_clip(tmp_path: Path, test_video: VideoClip):
    fp = str(tmp_path / "test")
    # Write video should throw exception if it recieves no format
    with pytest.raises(ValueError):
        write_video(fp, test_video)


def test_save_invalid_ext_clip(tmp_path: Path, test_video: VideoClip):
    fp = str(tmp_path / "test.invalid")
    # Write video should throw exception if it recieves invalid format
    with pytest.raises(ValueError):
        write_video(fp, test_video)


def test_video_with_no_ext_converted(
    client: WeaveClient, tmp_path: Path, test_video: VideoClip
):
    video_path = str(tmp_path / "test.mp4")
    # Save an mp4 video
    write_video(video_path, test_video)
    # Copy to a new file with no extension
    test_path = str(tmp_path / "test")
    shutil.copyfile(video_path, test_path)

    # Load the video without extension
    clip = VideoFileClip(test_path)

    # Try to publish it - this should use DEFAULT_VIDEO_FORMAT (mp4)
    ref = weave.publish(clip)

    # Check that we can get it back
    # Use ref.get() directly instead of weave.ref(ref.uri()).get() to avoid
    # potential race conditions with ref resolution
    recovered = ref.get()
    assert isinstance(recovered, VideoClip)


def test_weave_op_video(tmp_path: Path, test_video: VideoClip):
    # Create a temporary file path
    fp = str(tmp_path / "test.mp4")

    # Use the temporary file path in the weave op
    @weave.op
    def save_video_op(clip: VideoClip, path: str):
        write_video(path, clip)
        return path

    # Call the weave op
    result = save_video_op(test_video, fp)
    # Check if the file was created
    assert os.path.exists(result)
    # Check if the video was written
    assert os.path.getsize(result) > 0


def test_video_publish(client: WeaveClient, test_video: VideoClip) -> None:
    ref = weave.publish(test_video)
    assert ref is not None

    gotten_video = weave.ref(ref.uri()).get()
    assert isinstance(gotten_video, VideoClip)

    # Compare video dimensions - handle list vs tuple
    gotten_size = gotten_video.size
    test_size = test_video.size

    if isinstance(gotten_size, list) and isinstance(test_size, tuple):
        assert tuple(gotten_size) == test_size
    elif isinstance(gotten_size, tuple) and isinstance(test_size, list):
        assert gotten_size == tuple(test_size)
    else:
        assert gotten_size == test_size

    # Since we can't easily compare video contents, we'll just check that it's a valid video
    assert gotten_video.duration == test_video.duration


class VideoWrapper(weave.Object):
    video: VideoClip


def test_video_as_property(client: WeaveClient, test_video: VideoClip) -> None:
    client.project = "test_video_as_property"

    video_wrapper = VideoWrapper(video=test_video)
    assert video_wrapper.video == test_video

    ref = weave.publish(video_wrapper)
    assert ref is not None

    gotten_video_wrapper = weave.ref(ref.uri()).get()
    assert isinstance(gotten_video_wrapper.video, VideoClip)

    # Handle difference in size representation (list vs tuple)
    gotten_size = gotten_video_wrapper.video.size
    test_size = test_video.size

    if isinstance(gotten_size, list) and isinstance(test_size, tuple):
        assert tuple(gotten_size) == test_size
    elif isinstance(gotten_size, tuple) and isinstance(test_size, list):
        assert gotten_size == tuple(test_size)
    else:
        assert gotten_size == test_size

    assert gotten_video_wrapper.video.duration == test_video.duration


def test_video_as_dataset_cell(client: WeaveClient, test_video: VideoClip) -> None:
    client.project = "test_video_as_dataset_cell"

    dataset = weave.Dataset(rows=weave.Table([{"video": test_video}]))
    assert dataset.rows[0]["video"] == test_video

    ref = weave.publish(dataset)
    assert ref is not None

    gotten_dataset = weave.ref(ref.uri()).get()
    assert isinstance(gotten_dataset.rows[0]["video"], VideoClip)

    # Handle difference in size representation (list vs tuple)
    gotten_size = gotten_dataset.rows[0]["video"].size
    test_size = test_video.size

    if isinstance(gotten_size, list) and isinstance(test_size, tuple):
        assert tuple(gotten_size) == test_size
    elif isinstance(gotten_size, tuple) and isinstance(test_size, list):
        assert gotten_size == tuple(test_size)
    else:
        assert gotten_size == test_size

    assert gotten_dataset.rows[0]["video"].duration == test_video.duration


@weave.op
def video_as_solo_output(publish_first: bool, video: VideoClip) -> VideoClip:
    if publish_first:
        weave.publish(video)
    return video


@weave.op
def video_as_input_and_output_part(in_video: VideoClip) -> dict:
    return {"out_video": in_video}


def test_video_as_call_io(client: WeaveClient, test_video: VideoClip) -> None:
    non_published_video = video_as_solo_output(publish_first=False, video=test_video)
    video_dict = video_as_input_and_output_part(non_published_video)

    assert isinstance(video_dict["out_video"], VideoClip)

    # Helper function to compare sizes
    def compare_sizes(size1, size2, context=""):
        if isinstance(size1, list) and isinstance(size2, tuple):
            assert tuple(size1) == size2, f"{context} size mismatch: {size1} != {size2}"
        elif isinstance(size1, tuple) and isinstance(size2, list):
            assert size1 == tuple(size2), f"{context} size mismatch: {size1} != {size2}"
        else:
            assert size1 == size2, f"{context} size mismatch: {size1} != {size2}"

    # Compare sizes with the helper function
    compare_sizes(video_dict["out_video"].size, test_video.size, "video_dict")

    video_as_solo_output_call = video_as_solo_output.calls()[0]
    video_as_input_and_output_part_call = video_as_input_and_output_part.calls()[0]

    compare_sizes(
        video_as_solo_output_call.output.size, test_video.size, "solo_output_call"
    )
    compare_sizes(
        video_as_input_and_output_part_call.inputs["in_video"].size,
        test_video.size,
        "input_call",
    )
    compare_sizes(
        video_as_input_and_output_part_call.output["out_video"].size,
        test_video.size,
        "output_part_call",
    )


def test_video_as_call_io_refs(client: WeaveClient, test_video: VideoClip) -> None:
    client.project = "test_video_as_call_io_refs"

    # Helper function to compare sizes
    def compare_sizes(size1, size2, context=""):
        if isinstance(size1, list) and isinstance(size2, tuple):
            assert tuple(size1) == size2, f"{context} size mismatch: {size1} != {size2}"
        elif isinstance(size1, tuple) and isinstance(size2, list):
            assert size1 == tuple(size2), f"{context} size mismatch: {size1} != {size2}"
        else:
            assert size1 == size2, f"{context} size mismatch: {size1} != {size2}"

    non_published_video = video_as_solo_output(publish_first=True, video=test_video)
    video_dict = video_as_input_and_output_part(non_published_video)

    assert isinstance(video_dict["out_video"], VideoClip)
    compare_sizes(video_dict["out_video"].size, test_video.size, "video_dict")

    video_as_solo_output_call = video_as_solo_output.calls()[0]
    video_as_input_and_output_part_call = video_as_input_and_output_part.calls()[0]

    compare_sizes(
        video_as_solo_output_call.output.size, test_video.size, "solo_output_call"
    )
    compare_sizes(
        video_as_input_and_output_part_call.inputs["in_video"].size,
        test_video.size,
        "input_call",
    )
    compare_sizes(
        video_as_input_and_output_part_call.output["out_video"].size,
        test_video.size,
        "output_part_call",
    )


def test_video_as_file(client: WeaveClient, tmp_path: Path) -> None:
    client.project = "test_video_as_file"

    # Use the existing test video file
    fp = tmp_path / "test_video.mp4"

    if not fp.exists():
        # If no test video exists, create one
        clip = ColorClip(size=(64, 64), color=(128, 0, 128), duration=1)
        clip.fps = 24
        clip.write_videofile(
            str(fp), codec="libx264", audio=False, verbose=False, logger=None
        )

    @weave.op
    def return_video_mp4(path: str):
        return VideoFileClip(path)

    @weave.op
    def accept_video_mp4(val):
        width, height = val.size
        return f"Video size: {width}x{height}"

    res = accept_video_mp4(return_video_mp4(str(fp)))
    assert res.startswith("Video size: ")


def make_random_video(video_size: tuple[int, int] = (64, 64), duration: float = 1.0):
    # Create a solid color clip
    clip = ColorClip(size=video_size, color=(128, 0, 128), duration=duration)
    clip.fps = 24
    return clip


@pytest.fixture
def dataset_ref(client):
    # This fixture represents a saved dataset containing videos
    n_rows = 3
    rows = weave.Table([{"video": make_random_video()} for _ in range(n_rows)])
    dataset = weave.Dataset(rows=rows)
    ref = weave.publish(dataset)

    return ref


@pytest.mark.asyncio
async def test_videos_in_dataset_for_evaluation(client, dataset_ref):
    dataset = dataset_ref.get()
    evaluation = weave.Evaluation(dataset=dataset)

    @weave.op
    def model(video: VideoClip) -> dict[str, str]:
        width, height = video.size
        return {"result": f"Video size: {width}x{height}"}

    # Expect that evaluation works for a ref-get'd dataset containing videos
    res = await evaluation.evaluate(model)

    assert isinstance(res, dict)
    assert "model_latency" in res
    assert "mean" in res["model_latency"]
    assert isinstance(res["model_latency"]["mean"], (int, float))


def test_videos_in_load_of_dataset(client):
    n_rows = 3
    # Create smaller duration videos to avoid encoding issues
    videos = [make_random_video(duration=0.1) for _ in range(n_rows)]
    rows = weave.Table([{"video": video} for video in videos])
    dataset = weave.Dataset(rows=rows)
    ref = weave.publish(dataset)

    dataset = ref.get()
    for i, (gotten_row, local_row) in enumerate(zip(dataset.rows, rows, strict=False)):
        assert isinstance(gotten_row["video"], VideoClip), (
            f"Row {i} video is not a VideoClip"
        )

        # Handle difference in size representation (list vs tuple)
        gotten_size = gotten_row["video"].size
        local_size = local_row["video"].size

        if isinstance(gotten_size, list) and isinstance(local_size, tuple):
            assert tuple(gotten_size) == local_size, (
                f"Row {i} size mismatch: {gotten_size} != {local_size}"
            )
        elif isinstance(gotten_size, tuple) and isinstance(local_size, list):
            assert gotten_size == tuple(local_size), (
                f"Row {i} size mismatch: {gotten_size} != {local_size}"
            )
        else:
            assert gotten_size == local_size, (
                f"Row {i} size mismatch: {gotten_size} != {local_size}"
            )

        # Duration may be rounded due to encoding limitations, especially with small durations
        # Allow some tolerance in comparison
        assert abs(gotten_row["video"].duration - videos[i].duration) < 0.05, (
            f"Row {i} duration too different: {gotten_row['video'].duration} != {videos[i].duration}"
        )


def test_video_format_from_filename():
    from weave.type_handlers.Video.video import get_format_from_filename

    assert get_format_from_filename("test.mp4") == VideoFormat.MP4
    assert get_format_from_filename("test.webm") == VideoFormat.WEBM
    assert get_format_from_filename("test.gif") == VideoFormat.GIF
    assert get_format_from_filename("test") == VideoFormat.UNSUPPORTED
    # Make sure it handles paths with just extensions
    assert get_format_from_filename(".mp4") == VideoFormat.MP4
    # Make sure it handles paths with multiple dots
    assert get_format_from_filename("test.something.mp4") == VideoFormat.MP4


@pytest.mark.skipif(
    sys.platform == "win32",
    reason="moviepy library uses /dev/null on Windows which doesn't exist",
)
def test_multiple_video_formats(
    client: WeaveClient, tmp_path: Path, test_video: VideoClip
):
    """Test that we can publish videos of different formats in the same session."""
    sample_mp4_path = str(tmp_path / "test.mp4")
    sample_gif_path = str(tmp_path / "test.gif")
    sample_webm_path = str(tmp_path / "test.webm")

    write_video(sample_mp4_path, test_video)
    write_video(sample_gif_path, test_video)
    write_video(sample_webm_path, test_video)

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
