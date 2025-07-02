import base64
import os
import tempfile
from pathlib import Path
from typing import Literal
from typing_extensions import Annotated

import pytest
import weave
from weave import Dataset
from weave.trace.table import Table
from weave.trace.weave_client import WeaveClient, get_ref
from weave.type_wrappers.Content.content import Content


TEST_FILE_DIR = os.path.join(os.path.dirname(__file__), "examples")

TEST_FILES = [
    ('file', 'png', 'image/png'),
    ('file', 'mp3', 'audio/mpeg'),
    ('file', 'mp4', 'video/mp4'),
    ('file', 'pdf', 'application/pdf'),
]


class TestWeaveContent:
    @pytest.mark.parametrize(["file", "extension", "mimetype"], TEST_FILES)
    def test_content_from_path(
        self, _: WeaveClient, file: str, extension: str, mimetype: str
    ):
        """Test creating Content from file path."""
        file_path = os.path.join(TEST_FILE_DIR, f"{file}.{extension}")

        # Test Content.from_path()
        content = Content.from_path(file_path)
        assert content is not None
        assert content.extension == extension
        assert content.mimetype == mimetype
        assert content.filename == f"{file}.{extension}"
        assert content.size > 0
        assert isinstance(content.data, bytes)
        assert content.path == file_path
        assert content.input_type == "str"
        assert content.input_category == "path"

    @pytest.mark.parametrize(["file", "extension", "mimetype"], TEST_FILES)
    def test_content_from_bytes(
        self, _: WeaveClient, file: str, extension: str, mimetype: str
    ):
        """Test creating Content from bytes."""
        file_path = os.path.join(TEST_FILE_DIR, f"{file}.{extension}")
        with open(file_path, 'rb') as f:
            file_bytes = f.read()

        # Test Content.from_bytes() with explicit type hint
        content = Content.from_bytes(file_bytes, extension)
        assert content is not None
        assert content.extension == extension
        assert content.mimetype == mimetype
        assert content.size == len(file_bytes)
        assert content.data == file_bytes
        assert content.input_type == "bytes"
        assert content.input_category == "data"

        # Test with mimetype as type hint
        content2 = Content.from_bytes(file_bytes, mimetype)
        assert content2.mimetype == mimetype

    @pytest.mark.parametrize(["file", "extension", "mimetype"], TEST_FILES)
    def test_content_from_base64(
        self, _: WeaveClient, file: str, extension: str, mimetype: str
    ):
        """Test creating Content from base64 encoded string."""
        file_path = os.path.join(TEST_FILE_DIR, f"{file}.{extension}")
        with open(file_path, 'rb') as f:
            file_bytes = f.read()

        # Create base64 encoded string
        b64_string = base64.b64encode(file_bytes).decode('utf-8')

        # Test Content() with base64 string
        content = Content(b64_string, extension)
        assert content is not None
        assert content.extension == extension
        assert content.mimetype == mimetype
        assert content.data == file_bytes
        assert content.encoding == "base64"
        assert content.input_type == "str"
        assert content.input_category == "base64"

    @pytest.mark.parametrize(["file", "extension", "mimetype"], TEST_FILES)
    def test_content_from_pathlib(
        self, _: WeaveClient, file: str, extension: str, mimetype: str
    ):
        """Test creating Content from pathlib.Path object."""
        file_path = Path(TEST_FILE_DIR) / f"{file}.{extension}"

        # Test Content() with Path object
        content = Content(file_path)
        assert content is not None
        assert content.extension == extension
        assert content.mimetype == mimetype
        assert content.filename == f"{file}.{extension}"
        assert content.path == str(file_path)
        assert content.input_type == "Path"
        assert content.input_category == "path"

    @pytest.mark.parametrize(["file", "extension", "mimetype"], TEST_FILES)
    def test_content_publish_and_retrieve(
        self, _: WeaveClient, file: str, extension: str, mimetype: str
    ):
        """Test publishing and retrieving Content objects."""
        file_path = os.path.join(TEST_FILE_DIR, f"{file}.{extension}")
        content = Content.from_path(file_path)

        # Publish the content
        ref = weave.publish(content, name=f"test_content_{extension}")
        assert ref is not None

        # Retrieve and verify
        retrieved = ref.get()
        assert isinstance(retrieved, Content)
        assert retrieved.data == content.data
        assert retrieved.extension == extension
        assert retrieved.mimetype == mimetype
        assert retrieved.size == content.size

    def test_content_in_dataset(self, _: WeaveClient):
        """Test Content objects as dataset values."""
        # Create Content objects for each test file
        rows = []
        for file, extension, mimetype in TEST_FILES:
            file_path = os.path.join(TEST_FILE_DIR, f"{file}.{extension}")
            content = Content.from_path(file_path)
            rows.append({
                "name": f"{file}.{extension}",
                "content": content,
                "expected_mimetype": mimetype
            })

        # Create and publish dataset
        dataset = Dataset(rows=Table(rows))
        ref = weave.publish(dataset, name="test_content_dataset")

        # Retrieve and verify
        retrieved_dataset = ref.get()
        assert len(retrieved_dataset.rows) == len(TEST_FILES)

        for row in retrieved_dataset.rows:
            assert isinstance(row["content"], Content)
            assert row["content"].mimetype == row["expected_mimetype"]
            # Verify data integrity
            original_path = os.path.join(TEST_FILE_DIR, row["name"])
            with open(original_path, 'rb') as f:
                original_data = f.read()
            assert row["content"].data == original_data

    @pytest.mark.parametrize(["file", "extension", "mimetype"], TEST_FILES)
    def test_content_in_ops(
        self, _: WeaveClient, file: str, extension: str, mimetype: str
    ):
        """Test Content as input/output of weave ops."""
        file_path = os.path.join(TEST_FILE_DIR, f"{file}.{extension}")

        # Op that returns Content with annotation
        @weave.op
        def load_content_annotated(path: str) -> Annotated[bytes, Content[Literal["pdf"]]]:
            return Path(path).read_bytes()

        # Op that returns Content object directly
        @weave.op
        def load_content_direct(path: str) -> Content:
            data = Path(path).read_bytes()
            return Content(data, extension)

        # Op that takes Content as input
        @weave.op
        def process_content(content: Content) -> dict:
            return {
                "size": content.size,
                "extension": content.extension,
                "mimetype": content.mimetype
            }

        # Test annotated return
        if extension == "pdf":
            result = load_content_annotated(file_path)
            # The op should return a Content object when published
            ref = get_ref(result)
            if ref:
                retrieved = ref.get()
                assert isinstance(retrieved, Content)

        # Test direct Content return
        content = load_content_direct(file_path)
        assert isinstance(content, Content)
        assert content.extension == extension

        # Test Content as input
        result = process_content(content)
        assert result["size"] == content.size
        assert result["extension"] == extension
        assert result["mimetype"] == mimetype

    def test_content_save_method(self, _: WeaveClient):
        """Test saving Content to a file."""
        # Use a small test file
        original_path = os.path.join(TEST_FILE_DIR, "file.png")
        content = Content.from_path(original_path)

        with tempfile.TemporaryDirectory() as tmpdir:
            # Test save without filename
            dest_path = os.path.join(tmpdir, "saved_file.png")
            content.save(dest_path)
            assert os.path.exists(dest_path)

            # Verify saved content
            with open(dest_path, 'rb') as f:
                saved_data = f.read()
            assert saved_data == content.data

            # Test save to directory (should use original filename)
            content_with_filename = Content.from_path(original_path)
            content_with_filename.save(tmpdir)
            expected_path = os.path.join(tmpdir, "file.png")
            assert os.path.exists(expected_path)

    def test_content_as_string(self, _: WeaveClient):
        """Test converting Content to string for text files."""
        # Create a text content
        text_data = "Hello, this is a test file!\nWith multiple lines."
        text_bytes = text_data.encode('utf-8')

        content = Content.from_bytes(text_bytes, "txt")
        assert content.as_string() == text_data

        # Test with different encoding
        content_utf16 = Content(text_bytes, encoding='utf-8')
        assert content_utf16.as_string() == text_data

    def test_content_metadata(self, _: WeaveClient):
        """Test Content metadata property."""
        file_path = os.path.join(TEST_FILE_DIR, "file.png")
        content = Content.from_path(file_path)

        metadata = content.metadata
        assert isinstance(metadata, dict)
        assert "data" not in metadata  # Raw data should be excluded
        assert metadata["size"] == content.size
        assert metadata["filename"] == "file.png"
        assert metadata["extension"] == "png"
        assert metadata["mimetype"] == "image/png"
        assert metadata["encoding"] == "utf-8"
        assert metadata["path"] == file_path

    def test_content_type_hint_variations(self, _: WeaveClient):
        """Test different type hint formats."""
        file_path = os.path.join(TEST_FILE_DIR, "file.png")
        with open(file_path, 'rb') as f:
            file_bytes = f.read()

        # Test with extension without dot
        content1 = Content(file_bytes, "png")
        assert content1.extension == "png"
        assert content1.mimetype == "image/png"

        # Test with extension with dot
        content2 = Content(file_bytes, ".png")
        assert content2.extension == "png"
        assert content2.mimetype == "image/png"

        # Test with mimetype
        content3 = Content(file_bytes, "image/png")
        assert content3.extension == "png"
        assert content3.mimetype == "image/png"

    def test_content_error_handling(self, _: WeaveClient):
        """Test error handling in Content class."""
        # Test with non-existent file
        with pytest.raises(FileNotFoundError):
            Content.from_path("/non/existent/file.txt")

        # Test with invalid base64
        with pytest.raises(Exception):  # Base64 decode error
            Content("invalid-base64-string!", "txt")

        # Test with None input
        with pytest.raises(TypeError):
            Content(None)

        # Test with unsupported input type
        with pytest.raises(TypeError):
            Content(12345)  # Integer not supported

    def test_content_with_kwargs(self, _: WeaveClient):
        """Test Content initialization with additional kwargs."""
        file_bytes = b"Test content"

        # Test with custom filename
        content = Content(file_bytes, "txt", filename="custom.txt")
        assert content.filename == "custom.txt"

        # Test with custom encoding
        content2 = Content(file_bytes, "txt", encoding="latin-1")
        assert content2.encoding == "latin-1"

    def test_content_postprocessing(self, _: WeaveClient):
        """Test that Content postprocessing works correctly in ops."""
        @weave.op
        def create_content_from_bytes(data: bytes, hint: str) -> Content:
            return Content(data, hint)

        test_data = b"Test content for postprocessing"
        result = create_content_from_bytes(test_data, "txt")

        assert isinstance(result, Content)
        assert result.data == test_data
        assert result.extension == "txt"
        assert result.mimetype == "text/plain"
