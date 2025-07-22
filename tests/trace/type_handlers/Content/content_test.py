import base64
import tempfile
from pathlib import Path

import pytest
from util import generate_media

import weave
from weave import Dataset
from weave.trace.table import Table
from weave.trace.weave_client import WeaveClient
from weave.type_wrappers.Content.content import Content


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
    file = "file.wav"
    file = generate_media("WAV")
    fn = tmp_path_factory.mktemp("data") / "file.wav"
    file.save(fn)
    return fn


# New parameterization list using fixture names
MEDIA_TEST_PARAMS = [
    ("image_file", "png", "image/png"),
    ("audio_file", "wav", "audio/x-wav"),
    ("video_file", "mp4", "video/mp4"),
    ("pdf_file", "pdf", "application/pdf"),
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
        assert content.path == str(file_path.resolve())
        assert content.input_type == "<class 'str'>"
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
        assert content.input_type == "<class 'bytes'>"
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
        assert content.input_type == "<class 'str'>"
        assert content.content_type == "base64"

    @pytest.mark.parametrize(
        ("fixture_name", "extension", "mimetype"), MEDIA_TEST_PARAMS
    )
    def test_content_from_pathlib(
        self, fixture_name: str, extension: str, mimetype: str, request
    ):
        """Test creating Content from pathlib.Path object."""
        file_path = request.getfixturevalue(fixture_name)

        # Test Content() with Path object
        content = Content(file_path)
        assert content is not None
        assert content.extension == extension
        assert content.mimetype == mimetype
        assert content.filename == file_path.name
        assert content.path == str(file_path.resolve())
        assert content.input_type in ["<class 'pathlib.PosixPath'>", "<class 'pathlib.Path'>"]
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

    def test_content_as_string(self):
        """Test converting Content to string for text files."""
        # Create a text content
        text_data = "Hello, this is a test file!\nWith multiple lines."

        content = Content.from_bytes(text_data.encode("utf-8"), extension="txt")
        # The content class doesn't have an as_string method in the new API
        # Instead we can decode the data directly
        assert content.data.decode("utf-8") == text_data

        # Test with different encoding
        content_utf16 = Content.from_bytes(text_data.encode("utf-16"), extension="txt", encoding="utf-16")
        assert content_utf16.data.decode("utf-16") == text_data

    def test_content_from_text(self):
        """Test creating Content from text string."""
        text_data = "Hello, this is a test file!\nWith multiple lines."
        
        # Test Content.from_text()
        content = Content.from_text(text_data, extension="txt")
        assert content is not None
        assert content.extension == "txt"
        assert content.mimetype == "text/plain"
        assert content.data == text_data.encode("utf-8")
        assert content.encoding == "utf-8"
        assert content.input_type == "<class 'str'>"
        assert content.content_type == "text"
        
        # Test with custom encoding
        content2 = Content.from_text(text_data, extension="txt", encoding="utf-16")
        assert content2.data == text_data.encode("utf-16")
        assert content2.encoding == "utf-16"

    def test_content_metadata(self, image_file):
        """Test Content extra metadata property."""
        metadata = {"test": "value", "author": "test_user"}
        content = Content.from_path(image_file, metadata=metadata)
        
        # Check that metadata was stored in extra field
        assert content.extra == metadata
        
        # Check other fields are accessible
        assert content.size > 0
        assert content.filename == "file.png"
        assert content.extension == "png"
        assert content.mimetype == "image/png"
        assert content.encoding == "utf-8"
        assert content.path == str(image_file.resolve())

    def test_content_type_hint_variations(self, image_file):
        """Test different type hint formats."""
        with open(image_file, "rb") as f:
            file_bytes = f.read()

        # Test with extension without dot
        content1 = Content.from_bytes(file_bytes, extension="png")
        assert content1.extension == "png"
        assert content1.mimetype == "image/png"

        # Test with extension with dot
        content2 = Content.from_bytes(file_bytes, extension=".png")
        assert content2.extension == "png"
        assert content2.mimetype == "image/png"

        # Test with mimetype
        content3 = Content.from_bytes(file_bytes, mimetype="image/png")
        assert content3.extension == "png"
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
        assert content.extra == metadata

        # Test with custom encoding
        content2 = Content.from_bytes(file_bytes, extension="txt", encoding="latin-1")
        assert content2.encoding == "latin-1"

    # The following tests did not rely on the parameterized files,
    # but are updated to use fixtures for consistency where applicable.

    # def test_content_save_and_retrieve(self, image_file, client: WeaveClient):
    #     """Test publishing and retrieving Content objects."""
    #     content = Content.from_path(image_file)
    #
    #     # Publish the content
    #     ref = weave.publish(content, name=f"test_content_{content.extension}")
    #     assert ref is not None
    #
    #     # Retrieve and verify
    #     retrieved = ref.get()
    #     assert isinstance(retrieved, Content)
    #     assert retrieved.data == content.data
    #     assert retrieved.extension == content.extension
    #     assert retrieved.mimetype == content.mimetype
    #     assert retrieved.size == content.size
    #
    # def test_content_in_dataset(
    #     self, image_file, audio_file, video_file, pdf_file, client: WeaveClient
    # ):
    #     """Test Content objects as dataset values."""
    #     rows = []
    #     original_files = {}
    #
    #     # Use fixtures to create content and store original data for verification
    #     for file_path in [image_file, audio_file, video_file, pdf_file]:
    #         content = Content.from_path(file_path)
    #         rows.append(
    #             {
    #                 "name": file_path.name,
    #                 "content": content,
    #                 "expected_mimetype": content.mimetype,
    #             }
    #         )
    #         original_files[file_path.name] = file_path.read_bytes()
    #
    #     # Create and publish dataset
    #     dataset = Dataset(rows=Table(rows))
    #     ref = weave.publish(dataset, name="test_content_dataset")
    #
    #     # Retrieve and verify
    #     retrieved_dataset = ref.get()
    #     assert len(retrieved_dataset.rows) == len(rows)
    #
    #     for row in retrieved_dataset.rows:
    #         assert isinstance(row["content"], Content)
    #         assert row["content"].mimetype == row["expected_mimetype"]
    #         # Verify data integrity
    #         original_data = original_files[row["name"]]
    #         assert row["content"].data == original_data
    #
    # def test_content_postprocessing(self, client: WeaveClient):
    #     """Test that Content postprocessing works correctly in ops."""
    #
    #     @weave.op
    #     def create_content_from_bytes(data: bytes, hint: str) -> Content:
    #         return Content.from_bytes(data, extension=hint)
    #
    #     test_data = b"Test content for postprocessing"
    #     result = create_content_from_bytes(test_data, "txt")
    #
    #     assert isinstance(result, Content)
    #     assert result.data == test_data
    #     assert result.extension == "txt"
    #     assert result.mimetype == "text/plain"  # Simplified in mock
