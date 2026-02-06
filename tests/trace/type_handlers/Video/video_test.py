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


def assert_video_sizes_equal(actual, expected, context=""):
    """Assert two video sizes are equal, handling list vs tuple differences.

    moviepy may return sizes as either lists or tuples depending on how the
    clip was loaded. This helper normalizes the comparison.
    """
    msg = f"{context} size mismatch: {actual} != {expected}" if context else ""
    assert tuple(actual) == tuple(expected), msg


@pytest.fixture
def track_clips():
    """Track VideoClip objects for automatic cleanup after the test.

    Prevents file handle leaks that cause PermissionError on Windows CI.
    Register any clip that needs cleanup by calling track_clips(clip).
    Returns the clip so it can be used inline: ``clip = track_clips(get_clip())``.
    """
    clips: list[VideoClip] = []

    def _track(clip):
        clips.append(clip)
        return clip

    yield _track

    for clip in reversed(clips):
        try:
            clip.close()
        except Exception:
            pass


@pytest.fixture
def test_video():
    """Create a test video clip and close it after the test."""
    clip = ColorClip(size=(64, 64), color=(128, 0, 128), duration=1)
    clip.fps = 24
    yield clip
    clip.close()


@pytest.mark.parametrize("extension", ["mp4", "webm", "gif"])
def test_save_clip(tmp_path: Path, test_video: VideoClip, extension: str):
    fp = str(tmp_path / f"test.{extension}")
    write_video(fp, test_video)
    # Check if the file was created
    assert os.path.exists(fp)
    # Check if the video was written
    assert os.path.getsize(fp) > 0


@pytest.mark.parametrize("filename", ["test", "test.invalid"])
def test_save_invalid_clip(tmp_path: Path, test_video: VideoClip, filename: str):
    fp = str(tmp_path / filename)
    # Write video should throw exception if it recieves invalid format
    with pytest.raises(ValueError):
        write_video(fp, test_video)


def test_video_with_no_ext_converted(
    client: WeaveClient, tmp_path: Path, test_video: VideoClip, track_clips
):
    """Publish a video with no file extension and verify it round-trips as mp4."""
    video_path = str(tmp_path / "test.mp4")
    write_video(video_path, test_video)

    test_path = str(tmp_path / "test")
    shutil.copyfile(video_path, test_path)

    clip = track_clips(VideoFileClip(test_path))
    ref = weave.publish(clip)

    recovered = track_clips(weave.ref(ref.uri()).get())
    assert isinstance(recovered, VideoClip)


def test_weave_op_video(tmp_path: Path, test_video: VideoClip):
    """Verify a weave op can write a video file."""
    fp = str(tmp_path / "test.mp4")

    @weave.op
    def save_video_op(clip: VideoClip, path: str):
        write_video(path, clip)
        return path

    result = save_video_op(test_video, fp)
    assert os.path.exists(result)
    assert os.path.getsize(result) > 0


def test_video_publish(client: WeaveClient, test_video: VideoClip, track_clips) -> None:
    """Publish a video clip directly and verify it round-trips."""
    ref = weave.publish(test_video)
    assert ref is not None

    gotten_video = track_clips(weave.ref(ref.uri()).get())
    assert isinstance(gotten_video, VideoClip)
    assert_video_sizes_equal(gotten_video.size, test_video.size)
    assert gotten_video.duration == test_video.duration


class VideoWrapper(weave.Object):
    video: VideoClip


def test_video_as_property(
    client: WeaveClient, test_video: VideoClip, track_clips
) -> None:
    """Publish a video as a property of a weave Object and verify round-trip."""
    client.project = "test_video_as_property"

    video_wrapper = VideoWrapper(video=test_video)
    assert video_wrapper.video == test_video

    ref = weave.publish(video_wrapper)
    assert ref is not None

    gotten_video_wrapper = weave.ref(ref.uri()).get()
    track_clips(gotten_video_wrapper.video)
    assert isinstance(gotten_video_wrapper.video, VideoClip)
    assert_video_sizes_equal(gotten_video_wrapper.video.size, test_video.size)
    assert gotten_video_wrapper.video.duration == test_video.duration


def test_video_as_dataset_cell(
    client: WeaveClient, test_video: VideoClip, track_clips
) -> None:
    """Publish a video inside a Dataset cell and verify round-trip."""
    client.project = "test_video_as_dataset_cell"

    dataset = weave.Dataset(rows=weave.Table([{"video": test_video}]))
    assert dataset.rows[0]["video"] == test_video

    ref = weave.publish(dataset)
    assert ref is not None

    gotten_dataset = weave.ref(ref.uri()).get()
    gotten_video = gotten_dataset.rows[0]["video"]
    track_clips(gotten_video)

    assert isinstance(gotten_video, VideoClip)
    assert_video_sizes_equal(gotten_video.size, test_video.size)
    assert gotten_video.duration == test_video.duration


@weave.op
def video_as_solo_output(publish_first: bool, video: VideoClip) -> VideoClip:
    if publish_first:
        weave.publish(video)
    return video


@weave.op
def video_as_input_and_output_part(in_video: VideoClip) -> dict:
    return {"out_video": in_video}


def test_video_as_call_io(client: WeaveClient, test_video: VideoClip) -> None:
    """Verify videos work as op inputs and outputs without pre-publishing."""
    non_published_video = video_as_solo_output(publish_first=False, video=test_video)
    video_dict = video_as_input_and_output_part(non_published_video)

    assert isinstance(video_dict["out_video"], VideoClip)
    assert_video_sizes_equal(
        video_dict["out_video"].size, test_video.size, "video_dict"
    )

    video_as_solo_output_call = video_as_solo_output.calls()[0]
    video_as_input_and_output_part_call = video_as_input_and_output_part.calls()[0]

    assert_video_sizes_equal(
        video_as_solo_output_call.output.size, test_video.size, "solo_output_call"
    )
    assert_video_sizes_equal(
        video_as_input_and_output_part_call.inputs["in_video"].size,
        test_video.size,
        "input_call",
    )
    assert_video_sizes_equal(
        video_as_input_and_output_part_call.output["out_video"].size,
        test_video.size,
        "output_part_call",
    )


def test_video_as_call_io_refs(client: WeaveClient, test_video: VideoClip) -> None:
    """Verify videos work as op inputs and outputs with pre-publishing (refs)."""
    client.project = "test_video_as_call_io_refs"

    non_published_video = video_as_solo_output(publish_first=True, video=test_video)
    video_dict = video_as_input_and_output_part(non_published_video)

    assert isinstance(video_dict["out_video"], VideoClip)
    assert_video_sizes_equal(
        video_dict["out_video"].size, test_video.size, "video_dict"
    )

    video_as_solo_output_call = video_as_solo_output.calls()[0]
    video_as_input_and_output_part_call = video_as_input_and_output_part.calls()[0]

    assert_video_sizes_equal(
        video_as_solo_output_call.output.size, test_video.size, "solo_output_call"
    )
    assert_video_sizes_equal(
        video_as_input_and_output_part_call.inputs["in_video"].size,
        test_video.size,
        "input_call",
    )
    assert_video_sizes_equal(
        video_as_input_and_output_part_call.output["out_video"].size,
        test_video.size,
        "output_part_call",
    )


def test_video_as_file(client: WeaveClient, tmp_path: Path, track_clips) -> None:
    """Verify VideoFileClip objects can be passed through weave ops."""
    client.project = "test_video_as_file"

    fp = tmp_path / "test_video.mp4"

    if not fp.exists():
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

    video = track_clips(return_video_mp4(str(fp)))
    res = accept_video_mp4(video)
    assert res.startswith("Video size: ")


def make_random_video(video_size: tuple[int, int] = (64, 64), duration: float = 1.0):
    """Create a solid color test clip."""
    clip = ColorClip(size=video_size, color=(128, 0, 128), duration=duration)
    clip.fps = 24
    return clip


@pytest.fixture
def dataset_ref(client):
    """Fixture that publishes a dataset containing video clips."""
    n_rows = 3
    rows = weave.Table([{"video": make_random_video()} for _ in range(n_rows)])
    dataset = weave.Dataset(rows=rows)
    ref = weave.publish(dataset)
    return ref


@pytest.mark.asyncio
async def test_videos_in_dataset_for_evaluation(client, dataset_ref):
    """Verify that evaluation works for a dataset containing videos."""
    dataset = dataset_ref.get()
    evaluation = weave.Evaluation(dataset=dataset)

    @weave.op
    def model(video: VideoClip) -> dict[str, str]:
        width, height = video.size
        return {"result": f"Video size: {width}x{height}"}

    res = await evaluation.evaluate(model)

    assert isinstance(res, dict)
    assert "model_latency" in res
    assert "mean" in res["model_latency"]
    assert isinstance(res["model_latency"]["mean"], (int, float))


def test_videos_in_load_of_dataset(client):
    """Verify videos survive a publish -> get round-trip inside a dataset."""
    n_rows = 3
    videos = [make_random_video(duration=0.1) for _ in range(n_rows)]
    rows = weave.Table([{"video": video} for video in videos])
    dataset = weave.Dataset(rows=rows)
    ref = weave.publish(dataset)

    dataset = ref.get()
    for i, (gotten_row, local_row) in enumerate(zip(dataset.rows, rows, strict=False)):
        assert isinstance(gotten_row["video"], VideoClip), (
            f"Row {i} video is not a VideoClip"
        )

        assert_video_sizes_equal(
            gotten_row["video"].size,
            local_row["video"].size,
            f"Row {i}",
        )

        # Duration may be rounded due to encoding limitations
        assert abs(gotten_row["video"].duration - videos[i].duration) < 0.05, (
            f"Row {i} duration too different: {gotten_row['video'].duration} != {videos[i].duration}"
        )


def test_video_format_from_filename():
    """Verify filename-to-format detection for supported and unsupported formats."""
    from weave.type_handlers.Video.video import get_format_from_filename

    assert get_format_from_filename("test.mp4") == VideoFormat.MP4
    assert get_format_from_filename("test.webm") == VideoFormat.WEBM
    assert get_format_from_filename("test.gif") == VideoFormat.GIF
    assert get_format_from_filename("test") == VideoFormat.UNSUPPORTED
    assert get_format_from_filename(".mp4") == VideoFormat.MP4
    assert get_format_from_filename("test.something.mp4") == VideoFormat.MP4


@pytest.mark.skipif(
    sys.platform == "win32",
    reason="moviepy library uses /dev/null on Windows which doesn't exist",
)
def test_multiple_video_formats(
    client: WeaveClient, tmp_path: Path, test_video: VideoClip, track_clips
):
    """Test that we can publish videos of different formats in the same session."""
    paths = {fmt: str(tmp_path / f"test.{fmt}") for fmt in ("mp4", "gif", "webm")}
    for path in paths.values():
        write_video(path, test_video)

    clips = {fmt: track_clips(VideoFileClip(p)) for fmt, p in paths.items()}

    refs = {fmt: weave.publish(clip) for fmt, clip in clips.items()}

    for fmt, ref in refs.items():
        recovered = track_clips(weave.ref(ref.uri()).get())
        assert isinstance(recovered, VideoClip), f"{fmt} recovery failed"


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
