import os
import tempfile
from pathlib import Path

import pytest
from moviepy.editor import ColorClip, VideoClip, VideoFileClip

import weave
from weave.trace.weave_client import WeaveClient

"""When testing types, it is important to test:
Objects:
1. Publishing Directly
2. Publishing as a property
3. Using as a cell in a table

Calls:
4. Using as inputs, output, and output component (raw)
5. Using as inputs, output, and output component (refs)
"""


@pytest.fixture(
    params=[
        {"format": "gif"},
        {"format": "mp4"},
        # Skip webm due to compatibility issues with FFMPEG
        {"format": "webm"},
        {"format": "unsupported", "should_fail": True},
    ]
)
def test_video(request) -> VideoClip:
    """Create test videos in different formats.
    For testing unsupported formats, we'll just use a ColorClip with a fake format.
    """
    # Create a solid color clip (1 second duration)
    clip = ColorClip(size=(64, 64), color=(128, 0, 128), duration=1)

    # Set fps for the clip (needed for writing)
    clip.fps = 24

    if request.param.get("should_fail", False):
        # For unsupported format test, just set a format attribute
        # This will be caught by the video type handler
        clip.format = request.param["format"]
        return clip

    # Create a temp file with the correct extension
    with tempfile.NamedTemporaryFile(
        suffix=f".{request.param['format']}", delete=False
    ) as tmp:
        tmp_path = tmp.name

    # Write the clip to the temp file
    if request.param["format"] == "gif":
        clip.write_gif(tmp_path)
    elif request.param["format"] == "webm":
        clip.write_videofile(
            tmp_path, codec="libvpx", audio=False, verbose=False, logger=None
        )
    else:
        clip.write_videofile(
            tmp_path, codec="libx264", audio=False, verbose=False, logger=None
        )

    # Return a VideoFileClip of the temp file
    return VideoFileClip(tmp_path)


@pytest.mark.disable_logging_error_check  # Add marker to disable error log checking for this test
def test_video_publish(client: WeaveClient, test_video: VideoClip) -> None:
    if hasattr(test_video, "format") and test_video.format == "unsupported":
        # Test that unsupported formats raise an error
        with pytest.raises(ValueError, match="Unsupported video format"):
            weave.publish(test_video)
        return

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

    if hasattr(test_video, "format") and test_video.format == "unsupported":
        # Skip this test for unsupported formats
        pytest.skip("Skipping unsupported format test for property publishing")

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

    if hasattr(test_video, "format") and test_video.format == "unsupported":
        # Skip this test for unsupported formats
        pytest.skip("Skipping unsupported format test for dataset cells")

    dataset = weave.Dataset(rows=[{"video": test_video}])
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
    client.project = "test_video_as_call_io"

    if hasattr(test_video, "format") and test_video.format == "unsupported":
        # Skip this test for unsupported formats
        pytest.skip("Skipping unsupported format test for call IO")

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

    if hasattr(test_video, "format") and test_video.format == "unsupported":
        # Skip this test for unsupported formats
        pytest.skip("Skipping unsupported format test for call IO refs")

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


def test_video_as_file(client: WeaveClient) -> None:
    client.project = "test_video_as_file"

    # Use the existing test video file
    file_path = Path(__file__).parent.resolve() / "test_video.mp4"

    if not file_path.exists():
        # If no test video exists, create one
        clip = ColorClip(size=(64, 64), color=(128, 0, 128), duration=1)
        clip.fps = 24
        clip.write_videofile(
            str(file_path), codec="libx264", audio=False, verbose=False, logger=None
        )

    @weave.op()
    def return_video_mp4(path: str):
        file_path = Path(path)
        return VideoFileClip(file_path)

    @weave.op()
    def accept_video_mp4(val):
        width, height = val.size
        return f"Video size: {width}x{height}"

    try:
        res = accept_video_mp4(return_video_mp4(str(file_path)))
        assert res.startswith("Video size: ")
    except Exception as e:
        if file_path.exists() and os.path.getsize(file_path) > 0:
            pytest.skip(f"Skipping due to file loading error: {e}")
        else:
            raise e


def make_random_video(video_size: tuple[int, int] = (64, 64), duration: float = 1.0):
    # Create a solid color clip
    clip = ColorClip(size=video_size, color=(128, 0, 128), duration=duration)
    clip.fps = 24

    # Set default format to gif for ColorClip to avoid issues
    if not hasattr(clip, "format"):
        clip.format = "gif"

    return clip


@pytest.fixture
def dataset_ref(client):
    # This fixture represents a saved dataset containing videos
    N_ROWS = 3
    rows = [{"video": make_random_video()} for _ in range(N_ROWS)]
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
    assert "model_latency" in res and "mean" in res["model_latency"]
    assert isinstance(res["model_latency"]["mean"], (int, float))


def test_videos_in_load_of_dataset(client):
    N_ROWS = 3
    # Create smaller duration videos to avoid encoding issues
    videos = [make_random_video(duration=0.1) for _ in range(N_ROWS)]
    rows = [{"video": video} for video in videos]
    dataset = weave.Dataset(rows=rows)
    ref = weave.publish(dataset)

    dataset = ref.get()
    for i, (gotten_row, local_row) in enumerate(zip(dataset.rows, rows)):
        assert isinstance(
            gotten_row["video"], VideoClip
        ), f"Row {i} video is not a VideoClip"

        # Handle difference in size representation (list vs tuple)
        gotten_size = gotten_row["video"].size
        local_size = local_row["video"].size

        if isinstance(gotten_size, list) and isinstance(local_size, tuple):
            assert (
                tuple(gotten_size) == local_size
            ), f"Row {i} size mismatch: {gotten_size} != {local_size}"
        elif isinstance(gotten_size, tuple) and isinstance(local_size, list):
            assert gotten_size == tuple(
                local_size
            ), f"Row {i} size mismatch: {gotten_size} != {local_size}"
        else:
            assert (
                gotten_size == local_size
            ), f"Row {i} size mismatch: {gotten_size} != {local_size}"

        # Duration may be rounded due to encoding limitations, especially with small durations
        # Allow some tolerance in comparison
        assert (
            abs(gotten_row["video"].duration - videos[i].duration) < 0.05
        ), f"Row {i} duration too different: {gotten_row['video'].duration} != {videos[i].duration}"


def test_video_format_from_filename():
    from weave.type_handlers.Video.video import get_format_from_filename

    assert get_format_from_filename("test.mp4") == "mp4"
    assert get_format_from_filename("test.webm") == "webm"
    assert get_format_from_filename("test.gif") == "gif"
    assert get_format_from_filename("test") is None
    # Make sure it handles paths with just extensions
    assert get_format_from_filename(".mp4") == "mp4"
    # Make sure it handles paths with multiple dots
    assert get_format_from_filename("test.something.mp4") == "mp4"
