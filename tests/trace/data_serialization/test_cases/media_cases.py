import os
import sys
import wave
from datetime import datetime, timezone

from moviepy.editor import VideoFileClip
from PIL import Image

import weave
from tests.trace.data_serialization.spec import SerializationTestCase
from weave.type_wrappers.Content.content import Content

audio_file_path = os.path.join(
    os.path.dirname(__file__),
    "..",
    "..",
    "type_handlers",
    "Audio",
    "examples",
    "audio.wav",
)
AUDIO_BYTES = open(audio_file_path, "rb").read()

video_file_path = os.path.join(
    os.path.dirname(__file__),
    "..",
    "..",
    "type_handlers",
    "Video",
    "test_video.mp4",
)
VIDEO_BYTES = open(video_file_path, "rb").read()


def markdown_equality_check(a, b):
    return a.markup == b.markup and a.code_theme == b.code_theme


media_cases = [
    # Datetime
    SerializationTestCase(
        id="datetime",
        runtime_object_factory=lambda: datetime(
            2025, 1, 1, 0, 0, 0, tzinfo=timezone.utc
        ),
        inline_call_param=True,
        is_legacy=False,
        exp_json={
            "_type": "CustomWeaveType",
            "weave_type": {"type": "datetime.datetime"},
            "load_op": "weave:///shawn/test-project/op/load_datetime.datetime:I5VxfLU7vHlucXe4FZJfpByq3ZURgFCB4AGRAbzJBiM",
            "val": "2025-01-01T00:00:00+00:00",
        },
        exp_objects=[
            {
                "object_id": "load_datetime.datetime",
                "digest": "I5VxfLU7vHlucXe4FZJfpByq3ZURgFCB4AGRAbzJBiM",
                "exp_val": {
                    "_type": "CustomWeaveType",
                    "weave_type": {"type": "Op"},
                    "files": {"obj.py": "CxQFcFPlpWhtgyAfl3OyBe8Pvg9siZOzi7RFr2SOApk"},
                },
            }
        ],
        exp_files=[
            {
                "digest": "CxQFcFPlpWhtgyAfl3OyBe8Pvg9siZOzi7RFr2SOApk",
                "exp_content": b'import weave\nfrom weave.trace.serialization.mem_artifact import MemTraceFilesArtifact\nfrom typing import Any\nimport datetime\n\n@weave.op\ndef load(artifact: MemTraceFilesArtifact, name: str, val: Any) -> datetime.datetime:\n    """Deserialize an ISO format string back to a datetime object with timezone."""\n    return datetime.datetime.fromisoformat(val)\n',
            }
        ],
    ),
    # Image (PIL.Image.Image)
    SerializationTestCase(
        id="image",
        runtime_object_factory=lambda: Image.new("RGB", (10, 10), "red"),
        inline_call_param=True,
        is_legacy=False,
        exp_json={
            "_type": "CustomWeaveType",
            "weave_type": {"type": "PIL.Image.Image"},
            "files": {
                "image.png": "eIObd4Xf1Od75ekC8UuDfJMb7nk0VSF5WPzyohXn5eQ"
                if sys.platform == "win32"
                else "Ac3YO5daeesZTxBfXf7DAKaQZ5IZysk2HvclN8sfwxQ"
            },
            "load_op": "weave:///shawn/test-project/op/load_PIL.Image.Image:G57ZLLyjNmBYuUiKcaFR2epBPvaTocSrl2I2ZjXKRMo",
        },
        exp_objects=[
            {
                "object_id": "load_PIL.Image.Image",
                "digest": "G57ZLLyjNmBYuUiKcaFR2epBPvaTocSrl2I2ZjXKRMo",
                "exp_val": {
                    "_type": "CustomWeaveType",
                    "weave_type": {"type": "Op"},
                    "files": {"obj.py": "oKyWpRrHWg5AtuM6dCGDiqzYY3OaozIwkLIx995b1s0"},
                },
            }
        ],
        exp_files=[
            {
                "digest": "oKyWpRrHWg5AtuM6dCGDiqzYY3OaozIwkLIx995b1s0",
                "exp_content": b'import weave\nfrom weave.trace.serialization.mem_artifact import MemTraceFilesArtifact\nfrom typing import Any\nfrom weave.utils.iterators import first\nimport PIL.Image as Image\n\n@weave.op\ndef load(artifact: MemTraceFilesArtifact, name: str, val: Any) -> Image.Image:\n    # Today, we assume there can only be 1 image in the artifact.\n    filename = first(artifact.path_contents)\n    if not filename.startswith("image."):\n        raise ValueError(f"Expected filename to start with \'image.\', got {filename}")\n\n    path = artifact.path(filename)\n    return Image.open(path)\n',
            },
            {
                "digest": "eIObd4Xf1Od75ekC8UuDfJMb7nk0VSF5WPzyohXn5eQ"
                if sys.platform == "win32"
                else "Ac3YO5daeesZTxBfXf7DAKaQZ5IZysk2HvclN8sfwxQ",
                "exp_content": b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\n\x00\x00\x00\n\x08\x02\x00\x00\x00\x02PX\xea\x00\x00\x00\x13IDATx\x9cc\xfc\xcf\x80\x0f0\xe1\x95e\x18\xa9\xd2\x00A,\x01\x13y\xed\xba&\x00\x00\x00\x00IEND\xaeB`\x82"
                if sys.platform == "win32"
                else b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\n\x00\x00\x00\n\x08\x02\x00\x00\x00\x02PX\xea\x00\x00\x00\x12IDATx\x9cc\xfc\xcf\x80\x0f0\xe1\x95\x1d\xb1\xd2\x00A,\x01\x13\xb1\ns\x13\x00\x00\x00\x00IEND\xaeB`\x82",
            },
        ],
        equality_check=lambda a, b: a.tobytes() == b.tobytes(),
    ),
    # Audio (weave.type_handlers.Audio.audio.Audio)
    SerializationTestCase(
        id="audio",
        runtime_object_factory=lambda: wave.open(audio_file_path, "rb"),
        inline_call_param=True,
        is_legacy=False,
        exp_json={
            "_type": "CustomWeaveType",
            "weave_type": {"type": "weave.type_handlers.Audio.audio.Audio"},
            "files": {
                "_metadata.json": "k3eN5qEgVIyMLbUc8sQrx1LRU0gxf7l6dD9LIoSoa0M",
                "audio.wav": "xfOhnNfgQxRzgWZ6DC1QEGt9vrJWcathymKPPZQmmIw",
            },
            "load_op": "weave:///shawn/test-project/op/load_weave.type_handlers.Audio.audio.Audio:TLsINgRZoZmdVCOnipG3ZxtONX2GwnXndow1Z2iuWbs",
        },
        exp_objects=[
            {
                "object_id": "load_weave.type_handlers.Audio.audio.Audio",
                "digest": "TLsINgRZoZmdVCOnipG3ZxtONX2GwnXndow1Z2iuWbs",
                "exp_val": {
                    "_type": "CustomWeaveType",
                    "weave_type": {"type": "Op"},
                    "files": {"obj.py": "Tc7t52CyPXGxXQLJmz0LdSApkcJotoRRCh0gt973MNM"},
                },
            }
        ],
        exp_files=[
            {
                "digest": "Tc7t52CyPXGxXQLJmz0LdSApkcJotoRRCh0gt973MNM",
                "exp_content": b'import weave\nfrom typing import Any\nimport json\nimport wave\nfrom typing import Generic\nfrom typing import Literal as SUPPORTED_FORMATS_TYPE\nimport base64\nfrom typing import cast\nfrom typing import Self\nfrom pathlib._local import Path\nimport os\n\nMETADATA_FILE_NAME = "_metadata.json"\n\nAUDIO_FILE_PREFIX = "audio."\n\nT = "~T"\n\ndef try_decode(data: str | bytes) -> bytes:\n    """Attempt to decode data as base64 or convert to bytes.\n\n    This function tries to decode the input as base64 first. If that fails,\n    it will return the data as bytes, converting if needed.\n\n    Args:\n        data: Input data as string or bytes, potentially base64 encoded\n\n    Returns:\n        bytes: The decoded data as bytes\n    """\n    try:\n        data = base64.b64decode(data, validate=True)\n    except binascii.Error:\n        pass\n\n    if isinstance(data, str):\n        data = data.encode("utf-8")\n\n    return data\n\nSUPPORTED_FORMATS = [\n    "mp3",\n    "wav"\n]\n\ndef get_format_from_filename(filename: str) -> str:\n    """Get the file format from a filename.\n\n    Args:\n        filename: The filename to extract the format from\n    Returns:\n        The format string or None if no extension is found\n    """\n    # Get last dot position\n    last_dot = filename.rfind(".")\n\n    # If there\'s no dot or it\'s the last character, return None\n    if last_dot == -1 or last_dot == len(filename) - 1:\n        return ""\n\n    return filename[last_dot + 1 :].lower()\n\nclass Audio(Generic[T]):\n    """A class representing audio data in a supported format (wav or mp3).\n\n    This class handles audio data storage and provides methods for loading from\n    different sources and exporting to files.\n\n    Attributes:\n        format: The audio format (currently supports \'wav\' or \'mp3\')\n        data: The raw audio data as bytes\n\n    Args:\n        data: The audio data (bytes or base64 encoded string)\n        format: The audio format (\'wav\' or \'mp3\')\n        validate_base64: Whether to attempt base64 decoding of the input data\n\n    Raises:\n        ValueError: If audio data is empty or format is not supported\n    """\n\n    # File Format\n    format: SUPPORTED_FORMATS_TYPE\n\n    # Raw audio data bytes\n    data: bytes\n\n    def __init__(\n        self,\n        data: bytes,\n        format: SUPPORTED_FORMATS_TYPE,\n        validate_base64: bool = True,\n    ) -> None:\n        if len(data) == 0:\n            raise ValueError("Audio data cannot be empty")\n\n        if validate_base64:\n            data = try_decode(data)\n\n        self.data = data\n        self.format = format\n\n    @classmethod\n    def from_data(cls, data: str | bytes, format: str) -> Self:\n        """Create an Audio object from raw data and specified format.\n\n        Args:\n            data: Audio data as bytes or base64 encoded string\n            format: Audio format (\'wav\' or \'mp3\')\n\n        Returns:\n            Audio: A new Audio instance\n\n        Raises:\n            ValueError: If format is not supported\n        """\n        data = try_decode(data)\n        if format not in list(map(str, SUPPORTED_FORMATS)):\n            raise ValueError("Unknown format {format}, must be one of: mp3 or wav")\n\n        # We already attempted to decode it as base64 and coerced to bytes so we can skip that step\n        return cls(\n            data=data,\n            format=cast(SUPPORTED_FORMATS_TYPE, format),\n            validate_base64=False,\n        )\n\n    @classmethod\n    def from_path(cls, path: str | bytes | Path | os.PathLike) -> Self:\n        """Create an Audio object from a file path.\n\n        Args:\n            path: Path to an audio file (must have .wav or .mp3 extension)\n\n        Returns:\n            Audio: A new Audio instance loaded from the file\n\n        Raises:\n            ValueError: If file doesn\'t exist or has unsupported extension\n        """\n        if isinstance(path, bytes):\n            path = path.decode()\n\n        if not os.path.exists(path):\n            raise ValueError(f"File {path} does not exist")\n\n        format_str = get_format_from_filename(str(path))\n        if format_str not in list(map(str, SUPPORTED_FORMATS)):\n            raise ValueError(\n                f"Invalid file path {path}, file must end in one of: mp3 or wav"\n            )\n\n        data = open(path, "rb").read()\n        return cls(data=data, format=cast(SUPPORTED_FORMATS_TYPE, format_str))\n\n    def export(self, path: str | bytes | Path | os.PathLike) -> None:\n        """Export audio data to a file.\n\n        Args:\n            path: Path where the audio file should be written\n        """\n        with open(path, "wb") as f:\n            f.write(self.data)\n\n@weave.op\ndef load(\n    artifact: MemTraceFilesArtifact, name: str, val: Any\n) -> wave.Wave_read | Audio:\n    """Load an audio object from a trace files artifact.\n\n    Args:\n        artifact: The artifact containing the audio data\n        name: Name of the audio file in the artifact\n\n    Returns:\n        Either a wave.Wave_read object or an Audio object, depending on the stored type\n\n    Raises:\n        ValueError: If no audio is found in the artifact\n    """\n    pytype = None\n    if artifact.path_contents.get(METADATA_FILE_NAME):\n        with open(artifact.path(METADATA_FILE_NAME)) as f:\n            pytype = json.load(f).get("_type")\n\n    for filename in artifact.path_contents:\n        path = artifact.path(filename)\n        if filename.startswith(AUDIO_FILE_PREFIX):\n            if (\n                pytype is None and filename.endswith(".wav")\n            ) or pytype == "wave.Wave_read":\n                return wave.open(path, "rb")\n            return Audio.from_path(path=path)\n\n    raise ValueError("No audio found for artifact")\n',
            },
            {
                "digest": "k3eN5qEgVIyMLbUc8sQrx1LRU0gxf7l6dD9LIoSoa0M",
                "exp_content": b'{"_type": "wave.Wave_read"}',
            },
            {
                "digest": "xfOhnNfgQxRzgWZ6DC1QEGt9vrJWcathymKPPZQmmIw",
                "exp_content": AUDIO_BYTES,
            },
        ],
        equality_check=lambda a, b: a.readframes(10) == b.readframes(10),
        python_version_code_capture=(3, 13),
    ),
    # Markdown
    # Here, we put both inline and file cases together so that the ref on Markdown
    # doesn't screw up parallel tests.
    SerializationTestCase(
        id="markdown",
        runtime_object_factory=lambda: {
            "inline": weave.Markdown("a" * 1024),
            "file": weave.Markdown("# Hello, world!"),
        },
        inline_call_param=True,
        is_legacy=False,
        exp_json={
            "inline": {
                "_type": "CustomWeaveType",
                "weave_type": {"type": "rich.markdown.Markdown"},
                "files": {"markup.md": "LtyYaEfiCbQBbhQabchxbTIHNQ9BaWk4LUMVOb8pLko"},
                "val": {"code_theme": "monokai"},
                "load_op": "weave:///shawn/test-project/op/load_rich.markdown.Markdown:MPwIZFHQYXdmosmxQXRt2G3MbawPv70hA7t5sBsRQy4",
            },
            "file": {
                "_type": "CustomWeaveType",
                "weave_type": {"type": "rich.markdown.Markdown"},
                "val": {"markup": "# Hello, world!", "code_theme": "monokai"},
                "load_op": "weave:///shawn/test-project/op/load_rich.markdown.Markdown:MPwIZFHQYXdmosmxQXRt2G3MbawPv70hA7t5sBsRQy4",
            },
        },
        exp_objects=[
            {
                "object_id": "load_rich.markdown.Markdown",
                "digest": "MPwIZFHQYXdmosmxQXRt2G3MbawPv70hA7t5sBsRQy4",
                "exp_val": {
                    "_type": "CustomWeaveType",
                    "weave_type": {"type": "Op"},
                    "files": {"obj.py": "bDUl9kLLYCdQ7dk15Y26cjzH6yVPPnN9TokEOpi6XTo"},
                },
            }
        ],
        exp_files=[
            {
                "digest": "LtyYaEfiCbQBbhQabchxbTIHNQ9BaWk4LUMVOb8pLko",
                "exp_content": b"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
            },
            {
                "digest": "bDUl9kLLYCdQ7dk15Y26cjzH6yVPPnN9TokEOpi6XTo",
                "exp_content": b'import weave\nfrom typing import Any\nfrom rich.markdown import Markdown\n\n@weave.op\ndef load(artifact: "MemTraceFilesArtifact", name: str, val: Any) -> Markdown:\n    """Load markdown from file and metadata."""\n    if "markup" in val:\n        markup = val["markup"]\n    else:\n        with artifact.open("markup.md", binary=False) as f:\n            markup = f.read()\n\n    kwargs = {}\n    if val and isinstance(val, dict) and "code_theme" in val:\n        kwargs["code_theme"] = val["code_theme"]\n\n    return Markdown(markup=markup, **kwargs)\n',
            },
        ],
        equality_check=lambda a, b: (
            markdown_equality_check(a["inline"], b["inline"])
            and markdown_equality_check(a["file"], b["file"])
        ),
        python_version_code_capture=(3, 13),
    ),
    # Video
    SerializationTestCase(
        id="video",
        runtime_object_factory=lambda: VideoFileClip(video_file_path),
        inline_call_param=True,
        is_legacy=False,
        exp_json={
            "_type": "CustomWeaveType",
            "weave_type": {"type": "moviepy.video.VideoClip.VideoClip"},
            "files": {"video.mp4": "Aoxws9QUryX0YiZ8ScTAyi4YzX2SO5QHTsLsYABBMjc"},
            "load_op": "weave:///shawn/test-project/op/load_moviepy.video.VideoClip.VideoClip:57nRXE8OTSrJCh4wBQDAu8LWHiaKrPXXGqcSiMuX33s",
        },
        exp_objects=[
            {
                "object_id": "load_moviepy.video.VideoClip.VideoClip",
                "digest": "57nRXE8OTSrJCh4wBQDAu8LWHiaKrPXXGqcSiMuX33s",
                "exp_val": {
                    "_type": "CustomWeaveType",
                    "weave_type": {"type": "Op"},
                    "files": {"obj.py": "ofKPFvVObRa0RDVb9LREAGLWgjxFdNLbW8chrT4PCGI"},
                },
            }
        ],
        exp_files=[
            {
                "digest": "ofKPFvVObRa0RDVb9LREAGLWgjxFdNLbW8chrT4PCGI",
                "exp_content": b'from weave.trace.serialization.mem_artifact import MemTraceFilesArtifact\nfrom typing import Any\nimport importlib\nimport weave.trace.serialization.serializer as serializer\nfrom enum import Enum\nimport shutil\nfrom typing import TypeIs\n\n_registered = true\n\ndef _dependencies_met() -> bool:\n    """Check if the dependencies are met.  This import is deferred to avoid\n    an expensive module import at the top level.\n    """\n    import sys\n\n    # First check if already imported\n    if "moviepy" in sys.modules:\n        return True\n    # Otherwise check if it can be imported\n    try:\n        return importlib.util.find_spec("moviepy") is not None\n    except (ValueError, ImportError):\n        return False\n\nclass VideoFormat(str, Enum):\n    """These are NOT the list of formats we accept from the user\n    Rather, these are the list of formats we can save to weave servers\n    If we detect that the file is in these formats, we copy it over directly\n    Otherwise, we encode it to one of these formats using ffmpeg (mp4 by default).\n    """\n\n    GIF = "gif"\n    MP4 = "mp4"\n    WEBM = "webm"\n    UNSUPPORTED = "unsupported"\n\n    def __str__(self) -> str:\n        return self.value\n\n    @classmethod\n    def _missing_(cls, value: Any) -> VideoFormat:\n        return cls.UNSUPPORTED\n\ndef get_format_from_filename(filename: str) -> VideoFormat:\n    """Get the file format from a filename.\n\n    Args:\n        filename: The filename to extract the format from\n\n    Returns:\n        The format string or None if no extension is found\n    """\n    # Get last dot position\n    last_dot = filename.rfind(".")\n\n    # If there\'s no dot or it\'s the last character, return None\n    if last_dot == -1 or last_dot == len(filename) - 1:\n        return VideoFormat.UNSUPPORTED\n\n    # Get the extension without the dot\n    return VideoFormat(filename[last_dot + 1 :])\n\nDEFAULT_VIDEO_FORMAT = "mp4"\n\ndef write_video(fp: str, clip: VideoClip) -> None:\n    """Takes a filepath and a VideoClip and writes the video to the file.\n    errors if the file does not end in a supported video extension.\n    """\n    try:\n        fps = clip.fps or 24\n    except Exception as _:\n        fps = 24\n\n    audio = clip.audio\n    fmt_str = get_format_from_filename(fp)\n    fmt = VideoFormat(fmt_str)\n\n    if fmt == VideoFormat.UNSUPPORTED:\n        raise ValueError(f"Unsupported video format: {fmt_str}")\n\n    if fmt == VideoFormat.GIF:\n        clip.write_gif(fp, fps=fps)\n        return\n    if fmt == VideoFormat.WEBM:\n        codec = "libvpx"\n    else:\n        codec = "libx264"\n\n    clip.write_videofile(\n        fp,\n        fps=fps,\n        codec=codec,\n        audio=audio,\n        verbose=False,\n        logger=None,\n    )\n\ndef _save_video_file_clip(obj: VideoFileClip, artifact: MemTraceFilesArtifact) -> None:\n    """Save a VideoFileClip to the artifact.\n\n    Args:\n        obj: The VideoFileClip\n        artifact: The artifact to save to\n        name: Ignored, see comment below\n    """\n    video_format = get_format_from_filename(obj.filename)\n\n    # Check if the format is known/supported. If not, set to unsupported\n    fmt = VideoFormat(video_format)\n    ext = fmt.value\n\n    if fmt == VideoFormat.UNSUPPORTED:\n        ext = DEFAULT_VIDEO_FORMAT.value\n\n    with artifact.writeable_file_path(f"video.{ext}") as fp:\n        if fmt == VideoFormat.UNSUPPORTED:\n            # If the format is unsupported, we need to convert it\n            write_video(fp, obj)\n        else:\n            # Copy the file directly if it\'s a supported format\n            shutil.copy(obj.filename, fp)\n\nDEFAULT_VIDEO_FORMAT = "mp4"\n\ndef _save_non_file_clip(obj: VideoClip, artifact: MemTraceFilesArtifact) -> None:\n    ext = DEFAULT_VIDEO_FORMAT.value\n    with artifact.writeable_file_path(f"video.{ext}") as fp:\n        # If the format is unsupported, we need to convert it\n        write_video(fp, obj)\n\ndef save(\n    obj: VideoClip,\n    artifact: MemTraceFilesArtifact,\n    name: str,\n) -> None:\n    """Save a VideoClip to the artifact.\n\n    Args:\n        obj: The VideoClip or VideoWithPreview to save\n        artifact: The artifact to save to\n        name: Ignored, see comment below\n    """\n    _ensure_registered()\n    from moviepy.editor import VideoFileClip\n\n    is_video_file = isinstance(obj, VideoFileClip)\n\n    try:\n        if is_video_file:\n            _save_video_file_clip(obj, artifact)\n        else:\n            _save_non_file_clip(obj, artifact)\n    except Exception as e:\n        raise ValueError(f"Failed to write video file with error: {e}") from e\n\ndef load(artifact: MemTraceFilesArtifact, name: str, val: Any) -> VideoClip:\n    """Load a VideoClip from the artifact.\n\n    Args:\n        artifact: The artifact to load from\n        name: Ignored, consistent with save method\n\n    Returns:\n        The loaded VideoClip\n    """\n    _ensure_registered()\n    from moviepy.editor import VideoFileClip\n\n    # Assume there can only be 1 video in the artifact\n    for filename in artifact.path_contents:\n        path = artifact.path(filename)\n        if filename.startswith("video."):\n            return VideoFileClip(path)\n\n    raise ValueError("No video or found for artifact")\n\ndef is_video_clip_instance(obj: Any) -> TypeIs[VideoClip]:\n    """Check if the object is any subclass of VideoClip."""\n    _ensure_registered()\n    from moviepy.editor import VideoClip\n\n    return isinstance(obj, VideoClip)\n\ndef _ensure_registered() -> None:\n    """Ensure the video type handler is registered if MoviePy is available."""\n    global _registered\n    if not _registered and _dependencies_met():\n        from moviepy.editor import VideoClip\n\n        serializer.register_serializer(VideoClip, save, load, is_video_clip_instance)\n        _registered = True\n\n@serializer.op\ndef load(artifact: MemTraceFilesArtifact, name: str, val: Any) -> VideoClip:\n    """Load a VideoClip from the artifact.\n\n    Args:\n        artifact: The artifact to load from\n        name: Ignored, consistent with save method\n\n    Returns:\n        The loaded VideoClip\n    """\n    _ensure_registered()\n    from moviepy.editor import VideoFileClip\n\n    # Assume there can only be 1 video in the artifact\n    for filename in artifact.path_contents:\n        path = artifact.path(filename)\n        if filename.startswith("video."):\n            return VideoFileClip(path)\n\n    raise ValueError("No video or found for artifact")\n',
            },
            {
                "digest": "Aoxws9QUryX0YiZ8ScTAyi4YzX2SO5QHTsLsYABBMjc",
                "exp_content": VIDEO_BYTES,
            },
        ],
        equality_check=lambda a, b: (
            a.duration == b.duration
        ),  # could do better, but this is a good start
        python_version_code_capture=(3, 13),
    ),
    # Content
    ## WAV Content
    SerializationTestCase(
        id="content: WAV",
        runtime_object_factory=lambda: Content.from_path(audio_file_path),
        inline_call_param=True,
        is_legacy=False,
        exp_json={
            "_type": "CustomWeaveType",
            "weave_type": {"type": "weave.type_wrappers.Content.content.Content"},
            "files": {
                "content": "xfOhnNfgQxRzgWZ6DC1QEGt9vrJWcathymKPPZQmmIw",
                "metadata.json": "v5gYkptifYVGd0JYbW3U0jYQPSKkLzEI3eamc0cnCG8"
                if sys.platform == "win32"
                else "0tY4LYkQE9BXzCQDItzaUoFLd3lesQ0RkuHNMuXQJIk",
            },
            "load_op": "weave:///shawn/test-project/op/load_weave.type_wrappers.Content.content.Content:rYNtROqXAlmInL2FMfYyc5E9lnGKYboE1rX3POB6okw",
        },
        exp_objects=[
            {
                "object_id": "load_weave.type_wrappers.Content.content.Content",
                "digest": "rYNtROqXAlmInL2FMfYyc5E9lnGKYboE1rX3POB6okw",
                "exp_val": {
                    "_type": "CustomWeaveType",
                    "weave_type": {"type": "Op"},
                    "files": {"obj.py": "Fq40XcU67vm2ddGsMKXYcyjAGKuPmKPvqkFUh1e763I"},
                },
            }
        ],
        exp_files=[
            {
                "digest": "v5gYkptifYVGd0JYbW3U0jYQPSKkLzEI3eamc0cnCG8"
                if sys.platform == "win32"
                else "0tY4LYkQE9BXzCQDItzaUoFLd3lesQ0RkuHNMuXQJIk",
                "exp_content": b'{"size": 88244, "mimetype": "audio/wav", "digest": "c5f3a19cd7e043147381667a0c2d50106b7dbeb25671ab61ca628f3d9426988c", "filename": "audio.wav", "content_type": "file", "input_type": "str", "encoding": "utf-8", "metadata": null, "extension": ".wav"}'
                if sys.platform == "win32"
                else b'{"size": 88244, "mimetype": "audio/x-wav", "digest": "c5f3a19cd7e043147381667a0c2d50106b7dbeb25671ab61ca628f3d9426988c", "filename": "audio.wav", "content_type": "file", "input_type": "str", "encoding": "utf-8", "metadata": null, "extension": ".wav"}',
            },
            {
                "digest": "xfOhnNfgQxRzgWZ6DC1QEGt9vrJWcathymKPPZQmmIw",
                "exp_content": AUDIO_BYTES,
            },
            {
                "digest": "Fq40XcU67vm2ddGsMKXYcyjAGKuPmKPvqkFUh1e763I",
                "exp_content": b'import weave\nfrom weave.trace.serialization.mem_artifact import MemTraceFilesArtifact\nfrom typing import Any\nimport json\n\n@weave.op\ndef load(artifact: MemTraceFilesArtifact, name: str, val: Any) -> Content:\n    from weave.type_wrappers.Content.content import Content\n    from weave.type_wrappers.Content.content_types import (\n        ResolvedContentArgs,\n        ResolvedContentArgsWithoutData,\n    )\n\n    metadata_path = artifact.path("metadata.json")\n\n    with open(metadata_path) as f:\n        metadata: ResolvedContentArgsWithoutData = json.load(f)\n\n    with open(artifact.path("content"), "rb") as f:\n        data = f.read()\n\n    resolved_args: ResolvedContentArgs = {"data": data, **metadata}\n\n    return Content._from_resolved_args(resolved_args)\n',
            },
        ],
        equality_check=lambda a, b: a.digest == b.digest,
    ),
    # LEGACY CASES
    SerializationTestCase(
        id="datetime (legacy)",
        runtime_object_factory=lambda: datetime(
            2025, 1, 1, 0, 0, 0, tzinfo=timezone.utc
        ),
        inline_call_param=True,
        is_legacy=True,
        exp_json={
            "_type": "CustomWeaveType",
            "load_op": "weave:///shawn/test-project/op/load_datetime.datetime:qfWIlyPcNsevFkkBtJ50m3oU37XyuIxfAh4nLmTWyGY",
            "val": "2025-01-01T00:00:00+00:00",
            "weave_type": {"type": "datetime.datetime"},
        },
        exp_objects=[
            {
                "object_id": "load_datetime.datetime",
                "digest": "qfWIlyPcNsevFkkBtJ50m3oU37XyuIxfAh4nLmTWyGY",
                "exp_val": {
                    "_type": "CustomWeaveType",
                    "weave_type": {"type": "Op"},
                    "files": {"obj.py": "zPdXpSluF0nK2TYUIjkzOq7FfXxFZ0Thtkcr91vznGQ"},
                },
            }
        ],
        exp_files=[
            {
                "digest": "zPdXpSluF0nK2TYUIjkzOq7FfXxFZ0Thtkcr91vznGQ",
                "exp_content": b'import weave\nimport datetime\n\n@weave.op\ndef load(encoded: str) -> datetime.datetime:\n    """Deserialize an ISO format string back to a datetime object with timezone."""\n    return datetime.datetime.fromisoformat(encoded)\n',
            }
        ],
    ),
    SerializationTestCase(
        id="image (legacy)",
        runtime_object_factory=lambda: Image.new("RGB", (10, 10), "red"),
        inline_call_param=False,
        is_legacy=True,
        exp_json={
            "_type": "CustomWeaveType",
            "weave_type": {"type": "PIL.Image.Image"},
            "files": {"image.png": "Ac3YO5daeesZTxBfXf7DAKaQZ5IZysk2HvclN8sfwxQ"},
            "load_op": "weave:///shawn/test-project/op/load_PIL.Image.Image:G57ZLLyjNmBYuUiKcaFR2epBPvaTocSrl2I2ZjXKRMo",
        },
        exp_objects=[
            {
                "object_id": "load_PIL.Image.Image",
                "digest": "G57ZLLyjNmBYuUiKcaFR2epBPvaTocSrl2I2ZjXKRMo",
                "exp_val": {
                    "_type": "CustomWeaveType",
                    "weave_type": {"type": "Op"},
                    "files": {"obj.py": "oKyWpRrHWg5AtuM6dCGDiqzYY3OaozIwkLIx995b1s0"},
                },
            }
        ],
        exp_files=[
            {
                "digest": "oKyWpRrHWg5AtuM6dCGDiqzYY3OaozIwkLIx995b1s0",
                "exp_content": b'import weave\nfrom weave.trace.serialization.mem_artifact import MemTraceFilesArtifact\nfrom typing import Any\nfrom weave.utils.iterators import first\nimport PIL.Image as Image\n\n@weave.op\ndef load(artifact: MemTraceFilesArtifact, name: str, val: Any) -> Image.Image:\n    # Today, we assume there can only be 1 image in the artifact.\n    filename = first(artifact.path_contents)\n    if not filename.startswith("image."):\n        raise ValueError(f"Expected filename to start with \'image.\', got {filename}")\n\n    path = artifact.path(filename)\n    return Image.open(path)\n',
            },
            {
                "digest": "Ac3YO5daeesZTxBfXf7DAKaQZ5IZysk2HvclN8sfwxQ",
                "exp_content": b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\n\x00\x00\x00\n\x08\x02\x00\x00\x00\x02PX\xea\x00\x00\x00\x12IDATx\x9cc\xfc\xcf\x80\x0f0\xe1\x95\x1d\xb1\xd2\x00A,\x01\x13\xb1\ns\x13\x00\x00\x00\x00IEND\xaeB`\x82",
            },
        ],
        equality_check=lambda a, b: a.tobytes() == b.tobytes(),
    ),
    SerializationTestCase(
        id="audio (legacy)",
        runtime_object_factory=lambda: wave.open(audio_file_path, "rb"),
        inline_call_param=True,
        is_legacy=True,
        exp_json={
            "_type": "CustomWeaveType",
            "weave_type": {"type": "weave.type_handlers.Audio.audio.Audio"},
            "files": {
                "_metadata.json": "k3eN5qEgVIyMLbUc8sQrx1LRU0gxf7l6dD9LIoSoa0M",
                "audio.wav": "xfOhnNfgQxRzgWZ6DC1QEGt9vrJWcathymKPPZQmmIw",
            },
            "load_op": "weave:///shawn/test-project/op/load_weave.type_handlers.Audio.audio.Audio:2XCXiwP2vl1CaxrsqvkIeD3IXl5cykwIMDYbeGGtL5Q",
        },
        exp_objects=[
            {
                "object_id": "load_weave.type_handlers.Audio.audio.Audio",
                "digest": "2XCXiwP2vl1CaxrsqvkIeD3IXl5cykwIMDYbeGGtL5Q",
                "exp_val": {
                    "_type": "CustomWeaveType",
                    "weave_type": {"type": "Op"},
                    "files": {"obj.py": "F2jHjeAWTHKKRcwQ46F1TW6k5yAmYO4953BXYidOJbY"},
                },
            }
        ],
        exp_files=[
            {
                "digest": "F2jHjeAWTHKKRcwQ46F1TW6k5yAmYO4953BXYidOJbY",
                "exp_content": b'import weave\nimport json\nimport wave\nfrom typing import Generic\nfrom typing import Literal as SUPPORTED_FORMATS_TYPE\nimport base64\nfrom typing import cast\nfrom pathlib._local import Path\nimport os\n\nMETADATA_FILE_NAME = "_metadata.json"\n\nAUDIO_FILE_PREFIX = "audio."\n\nT = "~T"\n\ndef try_decode(data: str | bytes) -> bytes:\n    """Attempt to decode data as base64 or convert to bytes.\n\n    This function tries to decode the input as base64 first. If that fails,\n    it will return the data as bytes, converting if needed.\n\n    Args:\n        data: Input data as string or bytes, potentially base64 encoded\n\n    Returns:\n        bytes: The decoded data as bytes\n    """\n    try:\n        data = base64.b64decode(data, validate=True)\n    except binascii.Error:\n        pass\n\n    if isinstance(data, str):\n        data = data.encode("utf-8")\n\n    return data\n\nSUPPORTED_FORMATS = [\n    "mp3",\n    "wav"\n]\n\ndef get_format_from_filename(filename: str) -> str:\n    """Get the file format from a filename.\n\n    Args:\n        filename: The filename to extract the format from\n    Returns:\n        The format string or None if no extension is found\n    """\n    # Get last dot position\n    last_dot = filename.rfind(".")\n\n    # If there\'s no dot or it\'s the last character, return None\n    if last_dot == -1 or last_dot == len(filename) - 1:\n        return ""\n\n    return filename[last_dot + 1 :].lower()\n\nclass Audio(Generic[T]):\n    """A class representing audio data in a supported format (wav or mp3).\n\n    This class handles audio data storage and provides methods for loading from\n    different sources and exporting to files.\n\n    Attributes:\n        format: The audio format (currently supports \'wav\' or \'mp3\')\n        data: The raw audio data as bytes\n\n    Args:\n        data: The audio data (bytes or base64 encoded string)\n        format: The audio format (\'wav\' or \'mp3\')\n        validate_base64: Whether to attempt base64 decoding of the input data\n\n    Raises:\n        ValueError: If audio data is empty or format is not supported\n    """\n\n    # File Format\n    format: SUPPORTED_FORMATS_TYPE\n\n    # Raw audio data bytes\n    data: bytes\n\n    def __init__(\n        self,\n        data: bytes,\n        format: SUPPORTED_FORMATS_TYPE,\n        validate_base64: bool = True,\n    ) -> None:\n        if len(data) == 0:\n            raise ValueError("Audio data cannot be empty")\n\n        if validate_base64:\n            data = try_decode(data)\n\n        self.data = data\n        self.format = format\n\n    @classmethod\n    def from_data(cls, data: str | bytes, format: str) -> Audio:\n        """Create an Audio object from raw data and specified format.\n\n        Args:\n            data: Audio data as bytes or base64 encoded string\n            format: Audio format (\'wav\' or \'mp3\')\n\n        Returns:\n            Audio: A new Audio instance\n\n        Raises:\n            ValueError: If format is not supported\n        """\n        data = try_decode(data)\n        if format not in list(map(str, SUPPORTED_FORMATS)):\n            raise ValueError("Unknown format {format}, must be one of: mp3 or wav")\n\n        # We already attempted to decode it as base64 and coerced to bytes so we can skip that step\n        return cls(\n            data=data,\n            format=cast(SUPPORTED_FORMATS_TYPE, format),\n            validate_base64=False,\n        )\n\n    @classmethod\n    def from_path(cls, path: str | bytes | Path | os.PathLike) -> Audio:\n        """Create an Audio object from a file path.\n\n        Args:\n            path: Path to an audio file (must have .wav or .mp3 extension)\n\n        Returns:\n            Audio: A new Audio instance loaded from the file\n\n        Raises:\n            ValueError: If file doesn\'t exist or has unsupported extension\n        """\n        if isinstance(path, bytes):\n            path = path.decode()\n\n        if not os.path.exists(path):\n            raise ValueError(f"File {path} does not exist")\n\n        format_str = get_format_from_filename(str(path))\n        if format_str not in list(map(str, SUPPORTED_FORMATS)):\n            raise ValueError(\n                f"Invalid file path {path}, file must end in one of: mp3 or wav"\n            )\n\n        data = open(path, "rb").read()\n        return cls(data=data, format=cast(SUPPORTED_FORMATS_TYPE, format_str))\n\n    def export(self, path: str | bytes | Path | os.PathLike) -> None:\n        """Export audio data to a file.\n\n        Args:\n            path: Path where the audio file should be written\n        """\n        with open(path, "wb") as f:\n            f.write(self.data)\n\n@weave.op\ndef load(artifact: MemTraceFilesArtifact, name: str) -> wave.Wave_read | Audio:\n    """Load an audio object from a trace files artifact.\n\n    Args:\n        artifact: The artifact containing the audio data\n        name: Name of the audio file in the artifact\n\n    Returns:\n        Either a wave.Wave_read object or an Audio object, depending on the stored type\n\n    Raises:\n        ValueError: If no audio is found in the artifact\n    """\n    pytype = None\n    if artifact.path_contents.get(METADATA_FILE_NAME):\n        with open(artifact.path(METADATA_FILE_NAME)) as f:\n            pytype = json.load(f).get("_type")\n\n    for filename in artifact.path_contents:\n        path = artifact.path(filename)\n        if filename.startswith(AUDIO_FILE_PREFIX):\n            if (\n                pytype is None and filename.endswith(".wav")\n            ) or pytype == "wave.Wave_read":\n                return wave.open(path, "rb")\n            return Audio.from_path(path=path)\n\n    raise ValueError("No audio found for artifact")\n',
            },
            {
                "digest": "k3eN5qEgVIyMLbUc8sQrx1LRU0gxf7l6dD9LIoSoa0M",
                "exp_content": b'{"_type": "wave.Wave_read"}',
            },
            {
                "digest": "xfOhnNfgQxRzgWZ6DC1QEGt9vrJWcathymKPPZQmmIw",
                "exp_content": AUDIO_BYTES,
            },
        ],
        equality_check=lambda a, b: a.readframes(10) == b.readframes(10),
        python_version_code_capture=(3, 13),
    ),
    SerializationTestCase(
        id="markdown (legacy)",
        runtime_object_factory=lambda: weave.Markdown("# Hello, world!"),
        inline_call_param=True,
        is_legacy=True,
        exp_json={
            "_type": "CustomWeaveType",
            "load_op": "weave:///shawn/test-project/op/load_rich.markdown.Markdown:K3Qbb0xXBuNKikOU3DYFUmeaEGVQZejAFbn5f1Ypuuo",
            "val": {"code_theme": "monokai", "markup": "# Hello, world!"},
            "weave_type": {"type": "rich.markdown.Markdown"},
        },
        exp_objects=[
            {
                "object_id": "load_rich.markdown.Markdown",
                "digest": "K3Qbb0xXBuNKikOU3DYFUmeaEGVQZejAFbn5f1Ypuuo",
                "exp_val": {
                    "_type": "CustomWeaveType",
                    "weave_type": {"type": "Op"},
                    "files": {"obj.py": "t9Y66w8NW5FQmjQnxpSRo8fMN8RSKEYrG6yQEmAQCZs"},
                },
            }
        ],
        exp_files=[
            {
                "digest": "t9Y66w8NW5FQmjQnxpSRo8fMN8RSKEYrG6yQEmAQCZs",
                "exp_content": b"import weave\nfrom typing import TypedDict\nfrom typing import NotRequired\nfrom rich.markdown import Markdown\n\nclass SerializedMarkdown(TypedDict):\n    markup: str\n    code_theme: NotRequired[str]\n\n@weave.op\ndef load(encoded: SerializedMarkdown) -> Markdown:\n    return Markdown(**encoded)\n",
            }
        ],
        equality_check=markdown_equality_check,
        python_version_code_capture=(3, 13),
    ),
    SerializationTestCase(
        id="video (legacy)",
        runtime_object_factory=lambda: VideoFileClip(video_file_path),
        inline_call_param=True,
        is_legacy=True,
        exp_json={
            "_type": "CustomWeaveType",
            "weave_type": {"type": "moviepy.video.VideoClip.VideoClip"},
            "files": {"video.mp4": "Aoxws9QUryX0YiZ8ScTAyi4YzX2SO5QHTsLsYABBMjc"},
            "load_op": "weave:///shawn/test-project/op/load_moviepy.video.VideoClip.VideoClip:l4uZahNcY9eftBBCimXVY6L0n4ZsRf0FVxT89LPuXrQ",
        },
        exp_objects=[
            {
                "object_id": "load_moviepy.video.VideoClip.VideoClip",
                "digest": "l4uZahNcY9eftBBCimXVY6L0n4ZsRf0FVxT89LPuXrQ",
                "exp_val": {
                    "_type": "CustomWeaveType",
                    "weave_type": {"type": "Op"},
                    "files": {"obj.py": "qsJFgYKKFWQAFA9xpVH84iPfYblL8b2Hrqef1YIm4QU"},
                },
            }
        ],
        exp_files=[
            {
                "digest": "qsJFgYKKFWQAFA9xpVH84iPfYblL8b2Hrqef1YIm4QU",
                "exp_content": b'from weave.trace.serialization.mem_artifact import MemTraceFilesArtifact\nimport importlib\nimport weave.trace.serialization.serializer as serializer\nfrom enum import Enum\nfrom typing import Any\nimport shutil\nfrom typing import TypeIs\n\n_registered = true\n\ndef _dependencies_met() -> bool:\n    """Check if the dependencies are met.  This import is deferred to avoid\n    an expensive module import at the top level.\n    """\n    import sys\n\n    # First check if already imported\n    if "moviepy" in sys.modules:\n        return True\n    # Otherwise check if it can be imported\n    try:\n        return importlib.util.find_spec("moviepy") is not None\n    except (ValueError, ImportError):\n        return False\n\nclass VideoFormat(str, Enum):\n    """These are NOT the list of formats we accept from the user\n    Rather, these are the list of formats we can save to weave servers\n    If we detect that the file is in these formats, we copy it over directly\n    Otherwise, we encode it to one of these formats using ffmpeg (mp4 by default).\n    """\n\n    GIF = "gif"\n    MP4 = "mp4"\n    WEBM = "webm"\n    UNSUPPORTED = "unsupported"\n\n    def __str__(self) -> str:\n        return self.value\n\n    @classmethod\n    def _missing_(cls, value: Any) -> VideoFormat:\n        return cls.UNSUPPORTED\n\ndef get_format_from_filename(filename: str) -> VideoFormat:\n    """Get the file format from a filename.\n\n    Args:\n        filename: The filename to extract the format from\n\n    Returns:\n        The format string or None if no extension is found\n    """\n    # Get last dot position\n    last_dot = filename.rfind(".")\n\n    # If there\'s no dot or it\'s the last character, return None\n    if last_dot == -1 or last_dot == len(filename) - 1:\n        return VideoFormat.UNSUPPORTED\n\n    # Get the extension without the dot\n    return VideoFormat(filename[last_dot + 1 :])\n\nDEFAULT_VIDEO_FORMAT = "mp4"\n\ndef write_video(fp: str, clip: VideoClip) -> None:\n    """Takes a filepath and a VideoClip and writes the video to the file.\n    errors if the file does not end in a supported video extension.\n    """\n    try:\n        fps = clip.fps or 24\n    except Exception as _:\n        fps = 24\n\n    audio = clip.audio\n    fmt_str = get_format_from_filename(fp)\n    fmt = VideoFormat(fmt_str)\n\n    if fmt == VideoFormat.UNSUPPORTED:\n        raise ValueError(f"Unsupported video format: {fmt_str}")\n\n    if fmt == VideoFormat.GIF:\n        clip.write_gif(fp, fps=fps)\n        return\n    if fmt == VideoFormat.WEBM:\n        codec = "libvpx"\n    else:\n        codec = "libx264"\n\n    clip.write_videofile(\n        fp,\n        fps=fps,\n        codec=codec,\n        audio=audio,\n        verbose=False,\n        logger=None,\n    )\n\ndef _save_video_file_clip(obj: VideoFileClip, artifact: MemTraceFilesArtifact) -> None:\n    """Save a VideoFileClip to the artifact.\n\n    Args:\n        obj: The VideoFileClip\n        artifact: The artifact to save to\n        name: Ignored, see comment below\n    """\n    video_format = get_format_from_filename(obj.filename)\n\n    # Check if the format is known/supported. If not, set to unsupported\n    fmt = VideoFormat(video_format)\n    ext = fmt.value\n\n    if fmt == VideoFormat.UNSUPPORTED:\n        ext = DEFAULT_VIDEO_FORMAT.value\n\n    with artifact.writeable_file_path(f"video.{ext}") as fp:\n        if fmt == VideoFormat.UNSUPPORTED:\n            # If the format is unsupported, we need to convert it\n            write_video(fp, obj)\n        else:\n            # Copy the file directly if it\'s a supported format\n            shutil.copy(obj.filename, fp)\n\nDEFAULT_VIDEO_FORMAT = "mp4"\n\ndef _save_non_file_clip(obj: VideoClip, artifact: MemTraceFilesArtifact) -> None:\n    ext = DEFAULT_VIDEO_FORMAT.value\n    with artifact.writeable_file_path(f"video.{ext}") as fp:\n        # If the format is unsupported, we need to convert it\n        write_video(fp, obj)\n\ndef save(\n    obj: VideoClip,\n    artifact: MemTraceFilesArtifact,\n    name: str,\n) -> None:\n    """Save a VideoClip to the artifact.\n\n    Args:\n        obj: The VideoClip or VideoWithPreview to save\n        artifact: The artifact to save to\n        name: Ignored, see comment below\n    """\n    _ensure_registered()\n    from moviepy.editor import VideoFileClip\n\n    is_video_file = isinstance(obj, VideoFileClip)\n\n    try:\n        if is_video_file:\n            _save_video_file_clip(obj, artifact)\n        else:\n            _save_non_file_clip(obj, artifact)\n    except Exception as e:\n        raise ValueError(f"Failed to write video file with error: {e}") from e\n\ndef load(artifact: MemTraceFilesArtifact, name: str) -> VideoClip:\n    """Load a VideoClip from the artifact.\n\n    Args:\n        artifact: The artifact to load from\n        name: Ignored, consistent with save method\n\n    Returns:\n        The loaded VideoClip\n    """\n    _ensure_registered()\n    from moviepy.editor import VideoFileClip\n\n    # Assume there can only be 1 video in the artifact\n    for filename in artifact.path_contents:\n        path = artifact.path(filename)\n        if filename.startswith("video."):\n            return VideoFileClip(path)\n\n    raise ValueError("No video or found for artifact")\n\ndef is_video_clip_instance(obj: Any) -> TypeIs[VideoClip]:\n    """Check if the object is any subclass of VideoClip."""\n    _ensure_registered()\n    from moviepy.editor import VideoClip\n\n    return isinstance(obj, VideoClip)\n\ndef _ensure_registered() -> None:\n    """Ensure the video type handler is registered if MoviePy is available."""\n    global _registered\n    if not _registered and _dependencies_met():\n        from moviepy.editor import VideoClip\n\n        serializer.register_serializer(VideoClip, save, load, is_video_clip_instance)\n        _registered = True\n\n@serializer.op()\ndef load(artifact: MemTraceFilesArtifact, name: str) -> VideoClip:\n    """Load a VideoClip from the artifact.\n\n    Args:\n        artifact: The artifact to load from\n        name: Ignored, consistent with save method\n\n    Returns:\n        The loaded VideoClip\n    """\n    _ensure_registered()\n    from moviepy.editor import VideoFileClip\n\n    # Assume there can only be 1 video in the artifact\n    for filename in artifact.path_contents:\n        path = artifact.path(filename)\n        if filename.startswith("video."):\n            return VideoFileClip(path)\n\n    raise ValueError("No video or found for artifact")\n',
            },
            {
                "digest": "Aoxws9QUryX0YiZ8ScTAyi4YzX2SO5QHTsLsYABBMjc",
                "exp_content": VIDEO_BYTES,
            },
        ],
        equality_check=lambda a, b: (
            a.duration == b.duration
        ),  # could do better, but this is a good start
        python_version_code_capture=(3, 13),
    ),
    SerializationTestCase(
        id="content: WAV (legacy)",
        runtime_object_factory=lambda: Content.from_path(audio_file_path),
        inline_call_param=True,
        is_legacy=True,
        exp_json={
            "_type": "CustomWeaveType",
            "weave_type": {"type": "weave.type_wrappers.Content.content.Content"},
            "files": {
                "content": "xfOhnNfgQxRzgWZ6DC1QEGt9vrJWcathymKPPZQmmIw",
                "metadata.json": "v5gYkptifYVGd0JYbW3U0jYQPSKkLzEI3eamc0cnCG8"
                if sys.platform == "win32"
                else "0tY4LYkQE9BXzCQDItzaUoFLd3lesQ0RkuHNMuXQJIk",
            },
            "load_op": "weave:///shawn/test-project/op/load_weave.type_wrappers.Content.content.Content:mn7j2psDgjs1WbT1TUcqm8uOmy57vXx2q55DE6Mzxok",
        },
        exp_objects=[
            {
                "object_id": "load_weave.type_wrappers.Content.content.Content",
                "digest": "mn7j2psDgjs1WbT1TUcqm8uOmy57vXx2q55DE6Mzxok",
                "exp_val": {
                    "_type": "CustomWeaveType",
                    "weave_type": {"type": "Op"},
                    "files": {"obj.py": "YLa4BrYiztcCIeYklpe1uiCCBYZdTNYaVxTSdYcx46w"},
                },
            }
        ],
        exp_files=[
            {
                "digest": "v5gYkptifYVGd0JYbW3U0jYQPSKkLzEI3eamc0cnCG8"
                if sys.platform == "win32"
                else "0tY4LYkQE9BXzCQDItzaUoFLd3lesQ0RkuHNMuXQJIk",
                "exp_content": b'{"size": 88244, "mimetype": "audio/wav", "digest": "c5f3a19cd7e043147381667a0c2d50106b7dbeb25671ab61ca628f3d9426988c", "filename": "audio.wav", "content_type": "file", "input_type": "str", "encoding": "utf-8", "metadata": null, "extension": ".wav"}'
                if sys.platform == "win32"
                else b'{"size": 88244, "mimetype": "audio/x-wav", "digest": "c5f3a19cd7e043147381667a0c2d50106b7dbeb25671ab61ca628f3d9426988c", "filename": "audio.wav", "content_type": "file", "input_type": "str", "encoding": "utf-8", "metadata": null, "extension": ".wav"}',
            },
            {
                "digest": "xfOhnNfgQxRzgWZ6DC1QEGt9vrJWcathymKPPZQmmIw",
                "exp_content": AUDIO_BYTES,
            },
            {
                "digest": "YLa4BrYiztcCIeYklpe1uiCCBYZdTNYaVxTSdYcx46w",
                "exp_content": b'import weave\nfrom weave.trace.serialization.mem_artifact import MemTraceFilesArtifact\nimport json\n\n@weave.op\ndef load(artifact: MemTraceFilesArtifact, name: str) -> Content:\n    from weave.type_wrappers.Content.content import Content\n    from weave.type_wrappers.Content.content_types import (\n        ResolvedContentArgs,\n        ResolvedContentArgsWithoutData,\n    )\n\n    metadata_path = artifact.path("metadata.json")\n\n    with open(metadata_path) as f:\n        metadata: ResolvedContentArgsWithoutData = json.load(f)\n\n    with open(artifact.path("content"), "rb") as f:\n        data = f.read()\n\n    resolved_args: ResolvedContentArgs = {"data": data, **metadata}\n\n    return Content._from_resolved_args(resolved_args)\n',
            },
        ],
        equality_check=lambda a, b: a.digest == b.digest,
    ),
]
