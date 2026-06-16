import base64
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest
from util import generate_media

import weave
from weave import Dataset
from weave.trace.table import Table
from weave.type_wrappers.Content.content import Content
from weave.utils import http_requests as _http_requests


@pytest.fixture(scope="session")
def video_file(tmp_path_factory) -> Path:
    file = generate_media("MP4")
    fn = tmp_path_factory.mktemp("data") / "file.mp4"
    file.save(fn)
    return fn


@pytest.fixture(scope="session")
def image_file(tmp_path_factory) -> Path:
    file = generate_media("PNG")
    fn = tmp_path_factory.mktemp("data") / "file.png"
    file.save(fn)
    return fn


@pytest.fixture(scope="session")
def pdf_file(tmp_path_factory) -> Path:
    file = generate_media("PDF")
    fn = tmp_path_factory.mktemp("data") / "file.pdf"
    file.save(fn)
    return fn


@pytest.fixture(scope="session")
def audio_file(tmp_path_factory) -> Path:
    file = generate_media("WAV")
    fn = tmp_path_factory.mktemp("data") / "file.wav"
    file.save(fn)
    return fn


MEDIA_TEST_PARAMS = [
    ("image_file", ".png", "image/png"),
    ("audio_file", ".wav", "audio/wav"),
    ("video_file", ".mp4", "video/mp4"),
    ("pdf_file", ".pdf", "application/pdf"),
]


@pytest.mark.parametrize(("fixture_name", "extension", "mimetype"), MEDIA_TEST_PARAMS)
def test_content_from_path_str_and_pathlib(fixture_name, extension, mimetype, request):
    """from_path accepts both str and pathlib.Path with identical results."""
    file_path = request.getfixturevalue(fixture_name)

    for path_arg in (str(file_path), file_path):
        content = Content.from_path(path_arg)
        assert content is not None
        assert content.extension == extension
        assert content.mimetype == mimetype
        assert content.filename == file_path.name
        assert content.size > 0
        assert isinstance(content.data, bytes)
        assert content.content_type == "file"
        cls = type(path_arg)
        expected_input_type = (
            cls.__qualname__
            if cls.__module__ == "builtins"
            else f"{cls.__module__}.{cls.__qualname__}"
        )
        assert content.input_type == expected_input_type


@pytest.mark.parametrize(("fixture_name", "extension", "mimetype"), MEDIA_TEST_PARAMS)
def test_content_from_bytes_and_base64(fixture_name, extension, mimetype, request):
    """from_bytes (by extension and by mimetype) and from_base64 reproduce the file."""
    file_path = request.getfixturevalue(fixture_name)
    file_bytes = file_path.read_bytes()

    content = Content.from_bytes(file_bytes, extension=extension)
    assert content is not None
    assert content.extension == extension
    assert content.mimetype == mimetype
    assert content.size == len(file_bytes)
    assert content.data == file_bytes
    assert content.input_type == "bytes"
    assert content.content_type == "bytes"

    assert Content.from_bytes(file_bytes, mimetype=mimetype).mimetype == mimetype

    b64_string = base64.b64encode(file_bytes).decode("utf-8")
    b64_content = Content.from_base64(b64_string, extension=extension)
    assert b64_content is not None
    assert b64_content.extension == extension
    assert b64_content.mimetype == mimetype
    assert b64_content.data == file_bytes
    assert b64_content.encoding == "base64"
    assert b64_content.input_type == "str"
    assert b64_content.content_type == "base64"


@pytest.mark.parametrize(("fixture_name", "extension", "mimetype"), MEDIA_TEST_PARAMS)
def test_content_in_ops(fixture_name, extension, mimetype, request):
    """Content round-trips as both an op return value and an op input."""
    file_path = request.getfixturevalue(fixture_name)

    @weave.op
    def load_content_direct(path: str) -> Content:
        return Content.from_path(path)

    @weave.op
    def process_content(content: Content) -> dict:
        return {
            "size": content.size,
            "extension": content.extension,
            "mimetype": content.mimetype,
        }

    content = load_content_direct(str(file_path))
    assert isinstance(content, Content)
    assert content.extension == extension

    result = process_content(content)
    assert result["size"] == content.size
    assert result["extension"] == extension
    assert result["mimetype"] == mimetype


def test_content_save_method(image_file):
    """save() writes to an explicit filename and to a directory (original filename)."""
    content = Content.from_path(image_file)

    with tempfile.TemporaryDirectory() as tmpdir:
        dest_path = Path(tmpdir) / "saved_file.png"
        content.save(dest_path)
        assert dest_path.exists()
        assert dest_path.read_bytes() == content.data

        Content.from_path(image_file).save(tmpdir)
        assert (Path(tmpdir) / image_file.name).exists()


def test_content_from_text_and_as_string():
    """from_text honors encoding, and as_string decodes every encoding/edge case."""
    text_data = "Hello, this is a test file!\nWith multiple lines."

    content = Content.from_text(text_data, extension="txt")
    assert content is not None
    assert content.extension == ".txt"
    assert content.mimetype == "text/plain"
    assert content.data == text_data.encode("utf-8")
    assert content.encoding == "utf-8"
    assert content.input_type == "str"
    assert content.content_type == "text"
    assert content.as_string() == text_data

    content_utf16 = Content.from_text(text_data, extension=".txt", encoding="utf-16")
    assert content_utf16.data == text_data.encode("utf-16")
    assert content_utf16.encoding == "utf-16"

    assert (
        Content.from_bytes(text_data.encode("utf-8"), extension="txt").as_string()
        == text_data
    )
    assert (
        Content.from_bytes(
            text_data.encode("utf-16"), extension="txt", encoding="utf-16"
        ).as_string()
        == text_data
    )
    assert (
        Content.from_bytes(
            text_data.encode("utf-32"), extension="txt", encoding="utf-32"
        ).as_string()
        == text_data
    )

    latin_text = "Café, naïve, résumé"
    assert (
        Content.from_bytes(
            latin_text.encode("latin-1"), extension="txt", encoding="latin-1"
        ).as_string()
        == latin_text
    )
    win_text = "Windows specific: ''"
    assert (
        Content.from_bytes(
            win_text.encode("windows-1252"), extension="txt", encoding="windows-1252"
        ).as_string()
        == win_text
    )

    b64_data = base64.b64encode(b"Binary data \x00\x01\x02").decode("ascii")
    assert Content.from_base64(b64_data, extension="bin").as_string() == b64_data
    b64_binary = base64.b64encode(bytes(range(256))).decode("ascii")
    assert Content.from_base64(b64_binary).as_string() == b64_binary

    assert Content.from_text("").as_string() == ""
    for txt in (
        "Special chars: \t\n\r€£¥",
        "こんにちは世界",
        "Hello 👋 World 🌍!",
        "\n        ╔═══╗\n        ║ART║\n        ╚═══╝\n        ",
        "Line1\nLine2\rLine3\r\nLine4",
    ):
        assert Content.from_text(txt).as_string() == txt

    long_text = "A" * 10000 + "\n" + "B" * 10000
    long_content = Content.from_text(long_text)
    assert long_content.as_string() == long_text
    assert len(long_content.as_string()) == 20001


def test_content_metadata_and_kwargs(image_file):
    """Metadata and encoding kwargs are stored, alongside the derived file fields."""
    metadata = {"test": "value", "author": "test_user"}
    content = Content.from_path(image_file, metadata=metadata)
    assert content.metadata == metadata
    assert content.size > 0
    assert content.filename == "file.png"
    assert content.extension == ".png"
    assert content.mimetype == "image/png"
    assert content.encoding == "utf-8"

    kw_meta = {"author": "test", "version": "1.0"}
    bytes_content = Content.from_bytes(
        b"Test content", extension="txt", metadata=kw_meta
    )
    assert bytes_content.metadata == kw_meta
    assert (
        Content.from_bytes(
            b"Test content", extension="txt", encoding="latin-1"
        ).encoding
        == "latin-1"
    )


def test_content_type_hint_variations(image_file):
    """from_bytes accepts extension w/o dot, extension w/ dot, and explicit mimetype."""
    file_bytes = image_file.read_bytes()
    for content in (
        Content.from_bytes(file_bytes, extension="png"),
        Content.from_bytes(file_bytes, extension=".png"),
        Content.from_bytes(file_bytes, mimetype="image/png"),
    ):
        assert content.extension == ".png"
        assert content.mimetype == "image/png"


def test_content_error_handling():
    """Missing file raises FileNotFoundError; bad base64 raises ValueError."""
    with pytest.raises(FileNotFoundError):
        Content.from_path("/non/existent/file.txt")
    with pytest.raises(ValueError, match="Invalid base64 data provided"):
        Content.from_base64("not-valid-base64!")


def test_empty_content_across_constructors():
    """Empty payloads via bytes/text/base64, with and without extension, are size 0."""
    empty = b""
    for ext, mimetype in (
        ("txt", "text/plain"),
        ("json", "application/json"),
        ("png", "image/png"),
    ):
        content = Content.from_bytes(empty, extension=ext)
        assert content.data == b""
        assert content.extension == f".{ext}"
        assert content.mimetype == mimetype
        assert content.size == 0
    assert Content.from_bytes(empty, extension="txt").as_string() == ""

    no_ext = Content.from_bytes(empty)
    assert no_ext.data == b""
    assert no_ext.extension == ""
    assert no_ext.mimetype == "application/octet-stream"
    assert no_ext.size == 0

    with tempfile.NamedTemporaryFile(delete=False, suffix="") as tmp:
        tmp_path = tmp.name
    try:
        content_file = Content.from_path(tmp_path)
        assert content_file.data == b""
        assert content_file.extension == ""
        assert content_file.mimetype == "application/octet-stream"
        assert content_file.size == 0
        assert content_file.filename == Path(tmp_path).name
    finally:
        Path(tmp_path).unlink()

    text_empty = Content.from_text("", extension="txt")
    assert text_empty.data == b""
    assert text_empty.extension == ".txt"
    assert text_empty.size == 0
    assert text_empty.as_string() == ""

    text_no_ext = Content.from_text("")
    assert text_no_ext.data == b""
    assert text_no_ext.extension == ".txt"
    assert text_no_ext.size == 0

    b64_empty = Content.from_base64("", extension="bin")
    assert b64_empty.data == b""
    assert b64_empty.extension == ".bin"
    assert b64_empty.size == 0


def test_content_save_retrieve_and_dataset(
    image_file, audio_file, video_file, pdf_file, weave_active
):
    """Publish/retrieve a single Content and a Dataset of Content rows, verifying bytes."""
    content = Content.from_path(image_file)
    ref = weave.publish(content, name=f"test_content_{content.extension}")
    assert ref is not None
    retrieved = ref.get()
    assert isinstance(retrieved, Content)
    assert retrieved.data == content.data
    assert retrieved.extension == content.extension
    assert retrieved.mimetype == content.mimetype
    assert retrieved.size == content.size

    rows = []
    original_files = {}
    for file_path in [image_file, audio_file, video_file, pdf_file]:
        c = Content.from_path(file_path)
        rows.append(
            {"name": file_path.name, "content": c, "expected_mimetype": c.mimetype}
        )
        original_files[file_path.name] = file_path.read_bytes()

    dataset = Dataset(rows=Table(rows))
    ds_ref = weave.publish(dataset, name="test_content_dataset")
    retrieved_dataset = ds_ref.get()
    assert len(retrieved_dataset.rows) == len(rows)
    for row in retrieved_dataset.rows:
        assert isinstance(row["content"], Content)
        assert row["content"].mimetype == row["expected_mimetype"]
        assert row["content"].data == original_files[row["name"]]


def test_content_postprocessing(weave_active):
    """Content postprocessing works through an op that builds Content from bytes."""

    @weave.op
    def create_content_from_bytes(data: bytes, hint: str) -> Content:
        return Content.from_bytes(data, extension=hint)

    test_data = b"Test content for postprocessing"
    result = create_content_from_bytes(test_data, "txt")
    assert isinstance(result, Content)
    assert result.data == test_data
    assert result.extension == ".txt"
    assert result.mimetype == "text/plain"


def test_emoji_content():
    """Markdown text is detected via both from_text and _from_guess."""
    doc = """
My Awesome Emoji Document 👋
This is a simple document to show how you can use emojis in Markdown. It's a great way to add some personality and visual interest to your text! 🥳

I'm feeling pretty happy about it. 😄

My Goals for Today 🚀
Here is a list of things I want to accomplish:

✅ Finish my first task.

💡 Come up with a brilliant new idea.

🍕 Grab a slice of pizza for lunch.

🎉 Celebrate a small victory!

That's all for now. Have a great day! ☀️
"""
    assert Content.from_text(doc, extension=".md").mimetype == "text/markdown"
    # _from_guess feeds the text to is_valid_path, exercising its except branch.
    assert Content._from_guess(doc, extension=".md").mimetype == "text/markdown"


def test_content_from_url_basic_and_content_disposition():
    """from_url uses Content-Type; _from_guess honors a Content-Disposition filename."""
    txt_resp = _FakeResponse(
        b"hello world", {"Content-Type": "text/plain; charset=utf-8"}, encoding="utf-8"
    )
    with patch.object(_http_requests, "get", return_value=txt_resp):
        c = Content.from_url("https://example.com/path/to/test.txt")
    assert isinstance(c.data, bytes)
    assert c.data == b"hello world"
    assert c.mimetype == "text/plain"
    assert c.extension == ".txt"
    assert c.filename == "test.txt"
    assert c.size == len(b"hello world")
    assert c.content_type == "bytes"
    assert c.input_type == "str"

    pdf_resp = _FakeResponse(
        b"%PDF-1.4 Mock PDF bytes",
        {
            "Content-Type": "application/pdf",
            "Content-Disposition": 'attachment; filename="report.pdf"',
        },
        encoding=None,
    )
    with patch.object(_http_requests, "get", return_value=pdf_resp):
        c2 = Content._from_guess("http://example.com/download")
    assert c2.mimetype == "application/pdf"
    assert c2.extension == ".pdf"
    assert c2.filename == "report.pdf"
    assert c2.content_type == "bytes"
    assert c2.input_type == "str"


class _FakeHTTPError(Exception):
    """Raised by `_FakeResponse.raise_for_status` for non-2xx status codes."""


class _FakeResponse:
    """Stand-in for an http_requests response object in from_url tests."""

    def __init__(self, content: bytes, headers: dict, encoding: str | None):
        self.content = content
        self.headers = headers
        self.encoding = encoding
        self.status_code = 200

    def raise_for_status(self):
        if self.status_code >= 400:
            raise _FakeHTTPError("HTTP error")
