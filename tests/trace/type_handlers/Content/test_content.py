import base64
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest
from util import generate_media

import weave
from weave import Dataset
from weave.trace.table import Table
from weave.trace.weave_client import WeaveClient
from weave.type_wrappers.Content.content import Content
from weave.utils import http_requests as _http_requests


class _FakeHTTPError(Exception):
    """Custom exception used by FakeResponse.raise_for_status in tests."""

    pass


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


# New parameterization list using fixture names
# Note: Windows uses "audio/wav" while Unix uses "audio/x-wav"
MEDIA_TEST_PARAMS = [
    ("image_file", ".png", "image/png"),
    ("audio_file", ".wav", "audio/wav" if sys.platform == "win32" else "audio/x-wav"),
    ("video_file", ".mp4", "video/mp4"),
    ("pdf_file", ".pdf", "application/pdf"),
]


class TestWeaveContent:
    @pytest.mark.parametrize(
        ("fixture_name", "extension", "mimetype"), MEDIA_TEST_PARAMS
    )
    def test_content_from_path(
        self, fixture_name: str, extension: str, mimetype: str, request
    ):
        """Test creating Content from file path."""
        file_path = request.getfixturevalue(fixture_name)

        # Test Content.from_path()
        content = Content.from_path(str(file_path))
        assert content is not None
        assert content.extension == extension
        assert content.mimetype == mimetype
        assert content.filename == file_path.name
        assert content.size > 0
        assert isinstance(content.data, bytes)
        assert content.input_type == "str"
        assert content.content_type == "file"

    @pytest.mark.parametrize(
        ("fixture_name", "extension", "mimetype"), MEDIA_TEST_PARAMS
    )
    def test_content_from_bytes(
        self, fixture_name: str, extension: str, mimetype: str, request
    ):
        """Test creating Content from bytes."""
        file_path = request.getfixturevalue(fixture_name)
        file_bytes = file_path.read_bytes()

        # Test Content.from_bytes() with extension
        content = Content.from_bytes(file_bytes, extension=extension)
        assert content is not None
        assert content.extension == extension
        assert content.mimetype == mimetype
        assert content.size == len(file_bytes)
        assert content.data == file_bytes
        assert content.input_type == "bytes"
        assert content.content_type == "bytes"

        # Test with mimetype
        content2 = Content.from_bytes(file_bytes, mimetype=mimetype)
        assert content2.mimetype == mimetype

    @pytest.mark.parametrize(
        ("fixture_name", "extension", "mimetype"), MEDIA_TEST_PARAMS
    )
    def test_content_from_base64(
        self, fixture_name: str, extension: str, mimetype: str, request
    ):
        """Test creating Content from base64 encoded string."""
        file_path = request.getfixturevalue(fixture_name)
        file_bytes = file_path.read_bytes()

        # Create base64 encoded string
        b64_string = base64.b64encode(file_bytes).decode("utf-8")

        # Test Content.from_base64() with base64 string
        content = Content.from_base64(b64_string, extension=extension)
        assert content is not None
        assert content.extension == extension
        assert content.mimetype == mimetype
        assert content.data == file_bytes
        assert content.encoding == "base64"
        assert content.input_type == "str"
        assert content.content_type == "base64"

    @pytest.mark.parametrize(
        ("fixture_name", "extension", "mimetype"), MEDIA_TEST_PARAMS
    )
    def test_content_from_pathlib(
        self, fixture_name: str, extension: str, mimetype: str, request
    ):
        """Test creating Content from pathlib.Path object."""
        file_path = request.getfixturevalue(fixture_name)

        # Test Content.from_path() with Path object
        content = Content.from_path(file_path)
        assert content is not None
        assert content.extension == extension
        assert content.mimetype == mimetype
        assert content.filename == file_path.name
        assert content.content_type == "file"

    def test_content_save_method(self, image_file):
        """Test saving Content to a file."""
        content = Content.from_path(image_file)

        with tempfile.TemporaryDirectory() as tmpdir:
            # Test save with filename
            dest_path = Path(tmpdir) / "saved_file.png"
            content.save(dest_path)
            assert dest_path.exists()

            # Verify saved content
            saved_data = dest_path.read_bytes()
            assert saved_data == content.data

            # Test save to directory (should use original filename)
            content_with_filename = Content.from_path(image_file)
            content_with_filename.save(tmpdir)
            expected_path = Path(tmpdir) / image_file.name
            assert expected_path.exists()

    @pytest.mark.parametrize(
        ("fixture_name", "extension", "mimetype"), MEDIA_TEST_PARAMS
    )
    def test_content_in_ops(
        self, fixture_name: str, extension: str, mimetype: str, request
    ):
        """Test Content as input/output of weave ops."""
        file_path = request.getfixturevalue(fixture_name)

        # Op that returns Content object directly
        @weave.op
        def load_content_direct(path: str) -> Content:
            return Content.from_path(path)

        # Op that takes Content as input
        @weave.op
        def process_content(content: Content) -> dict:
            return {
                "size": content.size,
                "extension": content.extension,
                "mimetype": content.mimetype,
            }

        # Test direct Content return
        content = load_content_direct(str(file_path))
        assert isinstance(content, Content)
        assert content.extension == extension

        # Test Content as input
        result = process_content(content)
        assert result["size"] == content.size
        assert result["extension"] == extension
        assert result["mimetype"] == mimetype

    def test_content_from_text(self):
        """Test creating Content from text string."""
        text_data = "Hello, this is a test file!\nWith multiple lines."

        # Test Content.from_text()
        content = Content.from_text(text_data, extension="txt")
        assert content is not None
        assert content.extension == ".txt"
        assert content.mimetype == "text/plain"
        assert content.data == text_data.encode("utf-8")
        assert content.encoding == "utf-8"
        assert content.input_type == "str"
        assert content.content_type == "text"

        # Test with custom encoding
        content2 = Content.from_text(text_data, extension=".txt", encoding="utf-16")
        assert content2.data == text_data.encode("utf-16")
        assert content2.encoding == "utf-16"

    def test_content_as_string(self):
        """Test converting Content to string for text files using as_string method."""
        # Test 1: Basic UTF-8 text content
        text_data = "Hello, this is a test file!\nWith multiple lines."
        content = Content.from_text(text_data)
        assert content.as_string() == text_data

        # Test 2: UTF-8 content from bytes
        content_bytes = Content.from_bytes(text_data.encode("utf-8"), extension="txt")
        assert content_bytes.as_string() == text_data

        # Test 3: UTF-16 encoded content
        content_utf16 = Content.from_bytes(
            text_data.encode("utf-16"), extension="txt", encoding="utf-16"
        )
        assert content_utf16.as_string() == text_data

        # Test 4: Latin-1 encoded content
        latin_text = "Café, naïve, résumé"
        content_latin1 = Content.from_bytes(
            latin_text.encode("latin-1"), extension="txt", encoding="latin-1"
        )
        assert content_latin1.as_string() == latin_text

        # Test 5: Base64 encoded content
        b64_data = base64.b64encode(b"Binary data \x00\x01\x02").decode("ascii")
        content_b64 = Content.from_base64(b64_data, extension="bin")
        assert content_b64.as_string() == b64_data

        # Test 6: Empty content
        empty_content = Content.from_text("")
        assert empty_content.as_string() == ""

        # Test 7: Content with special characters
        special_chars = "Special chars: \t\n\r€£¥"
        content_special = Content.from_text(special_chars)
        assert content_special.as_string() == special_chars

        # Test 8: Japanese text (UTF-8)
        japanese_text = "こんにちは世界"
        content_japanese = Content.from_text(japanese_text)
        assert content_japanese.as_string() == japanese_text

        # Test 9: Emoji content
        emoji_text = "Hello 👋 World 🌍!"
        content_emoji = Content.from_text(emoji_text)
        assert content_emoji.as_string() == emoji_text

        # Test 10: ASCII art
        ascii_art = """
        ╔═══════════╗
        ║  ASCII    ║
        ║   ART     ║
        ╚═══════════╝
        """
        content_ascii_art = Content.from_text(ascii_art)
        assert content_ascii_art.as_string() == ascii_art

        # Test 11: Binary data through base64
        binary_data = bytes(list(range(256)))
        b64_binary = base64.b64encode(binary_data).decode("ascii")
        content_binary = Content.from_base64(b64_binary)
        assert content_binary.as_string() == b64_binary

        # Test 12: Multiline with different line endings
        multiline = "Line1\nLine2\rLine3\r\nLine4"
        content_multiline = Content.from_text(multiline)
        assert content_multiline.as_string() == multiline

        # Test 13: UTF-32 encoded content
        content_utf32 = Content.from_bytes(
            text_data.encode("utf-32"), extension="txt", encoding="utf-32"
        )
        assert content_utf32.as_string() == text_data

        # Test 14: Windows-1252 encoded content
        win_text = "Windows specific: ''"
        content_win1252 = Content.from_bytes(
            win_text.encode("windows-1252"), extension="txt", encoding="windows-1252"
        )
        assert content_win1252.as_string() == win_text

        # Test 15: Very long string
        long_text = "A" * 10000 + "\n" + "B" * 10000
        content_long = Content.from_text(long_text)
        assert content_long.as_string() == long_text
        assert (
            len(content_long.as_string()) == 20001
        )  # 10000 A's + 1 newline + 10000 B's

    def test_content_metadata(self, image_file):
        """Test Content extra metadata property."""
        metadata = {"test": "value", "author": "test_user"}
        content = Content.from_path(image_file, metadata=metadata)

        # Check that metadata was stored in extra field
        assert content.metadata == metadata

        # Check other fields are accessible
        assert content.size > 0
        assert content.filename == "file.png"
        assert content.extension == ".png"
        assert content.mimetype == "image/png"
        assert content.encoding == "utf-8"

    def test_content_type_hint_variations(self, image_file):
        """Test different type hint formats."""
        with open(image_file, "rb") as f:
            file_bytes = f.read()

        # Test with extension without dot
        content1 = Content.from_bytes(file_bytes, extension="png")
        assert content1.extension == ".png"
        assert content1.mimetype == "image/png"

        # Test with extension with dot
        content2 = Content.from_bytes(file_bytes, extension=".png")
        assert content2.extension == ".png"
        assert content2.mimetype == "image/png"

        # Test with mimetype
        content3 = Content.from_bytes(file_bytes, mimetype="image/png")
        assert content3.extension == ".png"
        assert content3.mimetype == "image/png"

    def test_content_error_handling(self):
        """Test error handling in Content class."""
        # Test with non-existent file
        with pytest.raises(FileNotFoundError):
            Content.from_path("/non/existent/file.txt")

        # Test with invalid base64
        with pytest.raises(ValueError):
            Content.from_base64("not-valid-base64!")

    def test_content_with_kwargs(self):
        """Test Content initialization with additional kwargs."""
        file_bytes = b"Test content"

        # Test with custom metadata
        metadata = {"author": "test", "version": "1.0"}
        content = Content.from_bytes(file_bytes, extension="txt", metadata=metadata)
        assert content.metadata == metadata

        # Test with custom encoding
        content2 = Content.from_bytes(file_bytes, extension="txt", encoding="latin-1")
        assert content2.encoding == "latin-1"

    def test_content_save_and_retrieve(self, image_file, client: WeaveClient):
        """Test publishing and retrieving Content objects."""
        content = Content.from_path(image_file)

        # Publish the content
        ref = weave.publish(content, name=f"test_content_{content.extension}")
        assert ref is not None

        # Retrieve and verify
        retrieved = ref.get()
        assert isinstance(retrieved, Content)
        assert retrieved.data == content.data
        assert retrieved.extension == content.extension
        assert retrieved.mimetype == content.mimetype
        assert retrieved.size == content.size

    def test_content_in_dataset(
        self, image_file, audio_file, video_file, pdf_file, client: WeaveClient
    ):
        """Test Content objects as dataset values."""
        rows = []
        original_files = {}

        # Use fixtures to create content and store original data for verification
        for file_path in [image_file, audio_file, video_file, pdf_file]:
            content = Content.from_path(file_path)
            rows.append(
                {
                    "name": file_path.name,
                    "content": content,
                    "expected_mimetype": content.mimetype,
                }
            )
            original_files[file_path.name] = file_path.read_bytes()

        # Create and publish dataset
        dataset = Dataset(rows=Table(rows))
        ref = weave.publish(dataset, name="test_content_dataset")

        # Retrieve and verify
        retrieved_dataset = ref.get()
        assert len(retrieved_dataset.rows) == len(rows)

        for row in retrieved_dataset.rows:
            assert isinstance(row["content"], Content)
            assert row["content"].mimetype == row["expected_mimetype"]
            # Verify data integrity
            original_data = original_files[row["name"]]
            assert row["content"].data == original_data

    def test_content_postprocessing(self, client: WeaveClient):
        """Test that Content postprocessing works correctly in ops."""

        @weave.op
        def create_content_from_bytes(data: bytes, hint: str) -> Content:
            return Content.from_bytes(data, extension=hint)

        test_data = b"Test content for postprocessing"
        result = create_content_from_bytes(test_data, "txt")

        assert isinstance(result, Content)
        assert result.data == test_data
        assert result.extension == ".txt"
        assert result.mimetype == "text/plain"  # Simplified in mock

    def test_empty_file_with_extension(self):
        """Test handling empty file with extension."""
        empty_data = b""

        # Test empty bytes with .txt extension
        content_txt = Content.from_bytes(empty_data, extension="txt")
        assert content_txt.data == b""
        assert content_txt.extension == ".txt"
        assert content_txt.mimetype == "text/plain"
        assert content_txt.size == 0
        assert content_txt.as_string() == ""

        # Test empty bytes with .json extension
        content_json = Content.from_bytes(empty_data, extension="json")
        assert content_json.data == b""
        assert content_json.extension == ".json"
        assert content_json.mimetype == "application/json"
        assert content_json.size == 0

        # Test empty bytes with .png extension
        content_png = Content.from_bytes(empty_data, extension="png")
        assert content_png.data == b""
        assert content_png.extension == ".png"
        assert content_png.mimetype == "image/png"
        assert content_png.size == 0

        # Test empty text content
        content_text = Content.from_text("", extension="txt")
        assert content_text.data == b""
        assert content_text.extension == ".txt"
        assert content_text.size == 0
        assert content_text.as_string() == ""

        # Test empty base64 content
        content_b64 = Content.from_base64("", extension="bin")
        assert content_b64.data == b""
        assert content_b64.extension == ".bin"
        assert content_b64.size == 0

    def test_file_no_extension_no_contents(self):
        """Test handling file with no extension and no contents."""
        empty_data = b""

        # Test empty bytes with no extension
        content_no_ext = Content.from_bytes(empty_data)
        assert content_no_ext.data == b""
        assert content_no_ext.extension == ""
        assert content_no_ext.mimetype == "application/octet-stream"  # Default mimetype
        assert content_no_ext.size == 0

        # Test empty file path with no extension
        with tempfile.NamedTemporaryFile(delete=False, suffix="") as tmp:
            tmp_path = tmp.name
            # File is created empty by default

        try:
            content_file = Content.from_path(tmp_path)
            assert content_file.data == b""
            assert content_file.extension == ""
            assert content_file.mimetype == "application/octet-stream"
            assert content_file.size == 0
            assert content_file.filename == Path(tmp_path).name
        finally:
            # Clean up
            Path(tmp_path).unlink()

        # Test empty text with no extension
        content_text_no_ext = Content.from_text("")
        assert content_text_no_ext.data == b""
        assert content_text_no_ext.extension == ".txt"  # Default for text
        assert content_text_no_ext.size == 0

    def test_emoji_content(self):
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
        # First do it with the correct constructor
        content = Content.from_text(doc, extension=".md")
        assert content.mimetype == "text/markdown"
        # Next guess from annotated value
        content = Content._from_guess(doc, extension=".md")
        assert content.mimetype == "text/markdown"

    def test_content_from_url_basic(self):
        class FakeResponse:
            def __init__(self):
                self.content = b"hello world"
                self.headers = {"Content-Type": "text/plain; charset=utf-8"}
                self.encoding = "utf-8"
                self.status_code = 200

            def raise_for_status(self):
                if self.status_code >= 400:
                    raise _FakeHTTPError("HTTP error")

        url = "https://example.com/path/to/test.txt"
        with patch.object(_http_requests, "get", return_value=FakeResponse()):
            c = Content.from_url(url)

        assert isinstance(c.data, bytes)
        assert c.data == b"hello world"
        assert c.mimetype == "text/plain"
        assert c.extension == ".txt"
        assert c.filename == "test.txt"
        assert c.size == len(b"hello world")
        assert c.content_type == "bytes"
        assert c.input_type == "str"

    def test__from_guess_http_url_with_content_disposition(self):
        class FakeResponse:
            def __init__(self):
                self.content = b"%PDF-1.4 Mock PDF bytes"
                self.headers = {
                    "Content-Type": "application/pdf",
                    "Content-Disposition": 'attachment; filename="report.pdf"',
                }
                self.encoding = None
                self.status_code = 200

            def raise_for_status(self):
                if self.status_code >= 400:
                    raise _FakeHTTPError("HTTP error")

        url = "http://example.com/download"
        with patch.object(_http_requests, "get", return_value=FakeResponse()):
            c = Content._from_guess(url)

        assert c.mimetype == "application/pdf"
        assert c.extension == ".pdf"
        assert c.filename == "report.pdf"
        assert c.content_type == "bytes"
        assert c.input_type == "str"
