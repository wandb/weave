from __future__ import annotations

import base64
import binascii
import os
import json # Added for exporting metadata
from pathlib import Path
from typing import (
    Annotated,
    Generic,
    TypeVar, # Correctly kept for MimeT
    TypedDict, # For ContentMetadata
    cast,
    Type,
    List,
)

# --- Import from our new mime_types module ---
# Assuming mime_types.py is in weave.content_types directory
from weave.content_types.mime_types import (
    guess_mime_type_from_path,
    get_supported_mime_types_for_category,
    get_default_extension_for_mime,
    MimeT, # Generic TypeVar for MIME types
    # Specific MIME type Literals for each class
    AudioMimeTypes, VideoMimeTypes, ImageMimeTypes, PdfMimeTypes,
    JsonMimeTypes, YamlMimeTypes, CsvMimeTypes, MarkdownMimeTypes,
    PlainTextMimeTypes, PythonMimeTypes, JavaScriptMimeTypes, TypeScriptMimeTypes
)

# --- Helper Functions (specific to Content class, not general MIME handling) ---
def get_extension_from_filename(filename: str) -> str:
    """Extracts the file extension (without the dot, lowercased) from a filename."""
    last_dot = filename.rfind(".")
    if last_dot == -1 or last_dot == len(filename) - 1:
        return ""
    return filename[last_dot + 1 :].lower()

def try_decode(data: str | bytes) -> bytes:
    """
    Attempts to decode data if it's a base64 encoded string,
    or encode a plain string to bytes. Returns bytes input as is.
    """
    if isinstance(data, str):
        try:
            return base64.b64decode(data, validate=True)
        except binascii.Error:
            return data.encode("utf-8") # Default to UTF-8 for string inputs
    return data

class ContentMetadata(TypedDict):
    """
    A TypedDict representing the metadata associated with a Content object.
    """
    original_path: str | None
    mimetype: str
    size: int # Size of the content data in bytes

# Define which media categories are considered text-based for normalization
TEXT_Content_CATEGORIES = {
    "json", "yaml", "csv", "markdown", "plaintext", 
    "python", "javascript", "typescript",
    # Add other text-based categories here if new classes are added (e.g., "html", "xml", "css")
}

# --- Content Base Class ---
class Content(Generic[MimeT]):
    """
    A generic base class for representing content data, using MIME types
    determined by the mime_types module. Text-based content loaded from paths
    will be normalized to UTF-8.
    """
    _Content_TYPE: str = "_base_media" # Internal key for Content_MIME_TYPE_REGISTRY

    media_category: str # User-facing category name, derived from _Content_TYPE
    mime_type: MimeT    # The specific MIME type of the media
    data: bytes         # The raw media data (normalized to UTF-8 for text types)
    _original_path: str | None = None # Optional path for file-based media

    def __init__(
        self,
        data: bytes | str,
        mime_type: MimeT, # Expects a validated MIME type string
        validate_base64: bool = True,
        _original_path: str | None = None, # To store path if loaded from file
        _expected_mime_types_list: List[str] | None = None # Internal use by classmethods
    ) -> None:
        cls_media_category_key = getattr(self.__class__, "_Content_TYPE", "_base_media")

        if validate_base64:
            processed_data = try_decode(data) # try_decode handles string to UTF-8 bytes
        elif isinstance(data, str):
            # If not validating base64 but still got a string, encode to UTF-8
            # This path is crucial for from_data when validate_base64 might be False
            # but data is a string.
            processed_data = data.encode("utf-8")
        else: # Assumed to be bytes
            processed_data = data

        if not processed_data:
            raise ValueError(f"{cls_media_category_key.capitalize()} data cannot be empty.")

        self.data = processed_data
        self.media_category = cls_media_category_key
        self._original_path = _original_path 

        current_expected_mime_types = _expected_mime_types_list or get_supported_mime_types_for_category(self.media_category)

        if not current_expected_mime_types:
             raise ValueError(f"No supported MIME types configured for media category '{self.media_category}'.")

        normalized_input_mime = str(mime_type).lower()
        if normalized_input_mime not in current_expected_mime_types:
            raise ValueError(
                f"Unsupported MIME type '{mime_type}' for {self.media_category} ({self.__class__.__name__}). "
                f"Supported MIME types are: {', '.join(current_expected_mime_types)}"
            )
        self.mime_type = mime_type

    @property
    def metadata(self) -> ContentMetadata:
        """
        Returns a dictionary containing metadata about the content.
        Size is based on the (potentially normalized) byte data.
        """
        return ContentMetadata(
            original_path=self._original_path,
            mimetype=str(self.mime_type), 
            size=len(self.data)
        )

    def export_metadata(self, path: str | Path | os.PathLike) -> str:
        """
        Exports the content's metadata to a specified file path as a JSON string.
        """
        path_str = os.fspath(path)
        metadata_to_export = self.metadata
        dir_name = os.path.dirname(path_str)
        if dir_name:
            os.makedirs(dir_name, exist_ok=True)
        with open(path_str, "w", encoding="utf-8") as f:
            json.dump(metadata_to_export, f, indent=4)
        print(f"Metadata exported to: {os.path.abspath(path_str)}")
        return os.path.abspath(path_str)

    @classmethod
    def _get_cls_media_category_key(cls) -> str:
        category_key = getattr(cls, "_Content_TYPE", "_base_media")
        if category_key == "_base_media" or not category_key:
            raise TypeError(
                f"Class {cls.__name__} must define a `_Content_TYPE` category key."
            )
        return category_key

    @classmethod
    def from_data(
        cls: Type[Content[MimeT]],
        data: str | bytes,
        mime_type: str,
    ) -> Content[MimeT]:
        """
        Creates a content object from raw or base64 encoded data.
        If data is a string, it's encoded to UTF-8.
        The user must specify the MIME type.
        """
        cls_media_category = cls._get_cls_media_category_key()
        supported_mime_types = get_supported_mime_types_for_category(cls_media_category)

        mime_type_lower = mime_type.lower()
        if not mime_type_lower in supported_mime_types:
            raise ValueError(
                f"Unsupported MIME type '{mime_type}' for {cls_media_category} ({cls.__name__}). "
                f"Supported: {', '.join(supported_mime_types)}"
            )
        # `__init__` will handle encoding string data to UTF-8 via `try_decode` or direct encoding.
        return cls(
            data=data, # Pass as is; __init__ handles string -> bytes conversion
            mime_type=cast(MimeT, mime_type_lower),
            validate_base64=True, # Let try_decode attempt base64 first
            _original_path=None, 
            _expected_mime_types_list=supported_mime_types
        )

    @classmethod
    def from_path(
        cls: Type[Content[MimeT]],
        path: str | Path | os.PathLike,
    ) -> Content[MimeT]:
        """
        Creates a content object from a file path.
        The MIME type is guessed. For text-based files, content is normalized to UTF-8.
        """
        cls_media_category = cls._get_cls_media_category_key()
        supported_mime_types = get_supported_mime_types_for_category(cls_media_category)
        path_str = os.fspath(path)

        if not os.path.exists(path_str):
            raise FileNotFoundError(f"File not found at path: {path_str}")

        guessed_mime_type = guess_mime_type_from_path(path_str)

        if not guessed_mime_type:
            file_ext = get_extension_from_filename(path_str)
            raise ValueError(
                f"Could not determine a recognized MIME type from path: {path_str}. "
                f"(Ext: '.{file_ext}'). Detector returned None."
            )

        guessed_mime_type_lower = guessed_mime_type.lower()
        if guessed_mime_type_lower not in supported_mime_types:
            raise ValueError(
                f"Guessed MIME type '{guessed_mime_type}' (from {path_str}) not supported "
                f"for {cls_media_category} ({cls.__name__}). "
                f"Supported: {', '.join(supported_mime_types)}"
            )

        with open(path_str, "rb") as f:
            file_data_bytes = f.read()

        # Normalize text-based content to UTF-8
        if cls_media_category in TEXT_Content_CATEGORIES:
            try:
                # Try decoding as UTF-8 first (handles BOMs correctly)
                decoded_string = file_data_bytes.decode('utf-8')
                # Re-encode to UTF-8 to ensure canonical form and remove BOMs for self.data
                file_data_bytes = decoded_string.encode('utf-8')
                # print(f"Info: Decoded '{path_str}' as UTF-8 and normalized.")
            except UnicodeDecodeError:
                try:
                    # Fallback to Latin-1 if UTF-8 fails
                    decoded_string = file_data_bytes.decode('latin-1')
                    # Convert the Latin-1 string to UTF-8 bytes for storage
                    file_data_bytes = decoded_string.encode('utf-8')
                    print(f"Info: Decoded '{path_str}' as Latin-1 and converted to UTF-8 for storage.")
                except UnicodeDecodeError:
                    # If both fail, keep original bytes and warn
                    print(
                        f"Warning: Could not decode '{path_str}' as UTF-8 or Latin-1. "
                        f"Storing raw bytes. get_content_as_string() might behave unexpectedly."
                    )

        return cls(
            data=file_data_bytes, # This is now potentially UTF-8 normalized for text
            mime_type=cast(MimeT, guessed_mime_type_lower),
            validate_base64=False, # Data is already bytes
            _original_path=path_str,
            _expected_mime_types_list=supported_mime_types
        )

    def export(self, path: str | Path | os.PathLike) -> str:
        """
        Exports the (potentially normalized) media data to a specified file path.
        """
        path_str = os.fspath(path)
        output_ext_from_path = get_extension_from_filename(path_str)
        expected_ext_for_mime = get_default_extension_for_mime(self.mime_type)

        final_path_str = path_str
        if not output_ext_from_path and expected_ext_for_mime:
            final_path_str += expected_ext_for_mime
            # print(f"Info: Appended '{expected_ext_for_mime}' to path. New path: '{final_path_str}'")
        elif output_ext_from_path and expected_ext_for_mime and ('.' + output_ext_from_path != expected_ext_for_mime):
            print(
                f"Warning: Exporting to file '{path_str}' with ext '.{output_ext_from_path}', "
                f"but MIME type '{self.mime_type}' typically uses '{expected_ext_for_mime}'. Data written."
            )

        dir_name = os.path.dirname(final_path_str)
        if dir_name:
            os.makedirs(dir_name, exist_ok=True)

        with open(final_path_str, "wb") as f:
            f.write(self.data) # self.data is already in its final byte form
        return final_path_str

    def get_content_as_string(self, encoding: str = "utf-8") -> str:
        """
        Decodes raw byte data (self.data) into a string.
        For text types normalized by from_path, self.data is UTF-8, so default encoding should work.
        For binary types or text types where normalization failed, this might raise an error
        if the data is not valid in the specified encoding.
        """
        try:
            return self.data.decode(encoding)
        except UnicodeDecodeError as e:
            # Provide more context in the error message
            # If it's a text category that failed normalization, this is more likely.
            category_info = f" (category: {self.media_category})" if self.media_category in TEXT_Content_CATEGORIES else ""
            raise UnicodeDecodeError(
                e.encoding, e.object, e.start, e.end,
                f"{e.reason} (MIME: {self.mime_type}, tried encoding: {encoding}{category_info})"
            ) from e

    def __repr__(self) -> str:
        return (
            f"{self.__class__.__name__}("
            f"category='{self.media_category}', "
            f"mime_type='{self.mime_type}', "
            f"data_size={len(self.data)} bytes, "
            f"original_path='{self._original_path}')"
        )

# Wrapper classes to differentiate between content types for frontend
class Audio(Content[AudioMimeTypes]):
    _Content_TYPE: str = "audio"
    def __init__(self, data: bytes | str, mime_type: AudioMimeTypes, validate_base64: bool = True, _original_path: str | None = None):
        super().__init__(data, mime_type=mime_type, validate_base64=validate_base64, _original_path=_original_path)
    @classmethod
    def from_data(cls, data: str | bytes, mime_type: str) -> Audio: return cast(Audio, super().from_data(data, mime_type))
    @classmethod
    def from_path(cls, path: str | Path | os.PathLike) -> Audio: return cast(Audio, super().from_path(path))

class Video(Content[VideoMimeTypes]):
    _Content_TYPE: str = "video"
    def __init__(self, data: bytes | str, mime_type: VideoMimeTypes, validate_base64: bool = True, _original_path: str | None = None):
        super().__init__(data, mime_type=mime_type, validate_base64=validate_base64, _original_path=_original_path)
    @classmethod
    def from_data(cls, data: str | bytes, mime_type: str) -> Video: return cast(Video, super().from_data(data, mime_type))
    @classmethod
    def from_path(cls, path: str | Path | os.PathLike) -> Video: return cast(Video, super().from_path(path))

class Image(Content[ImageMimeTypes]):
    _Content_TYPE: str = "image"
    def __init__(self, data: bytes | str, mime_type: ImageMimeTypes, validate_base64: bool = True, _original_path: str | None = None):
        super().__init__(data, mime_type=mime_type, validate_base64=validate_base64, _original_path=_original_path)
    @classmethod
    def from_data(cls, data: str | bytes, mime_type: str) -> Image: return cast(Image, super().from_data(data, mime_type))
    @classmethod
    def from_path(cls, path: str | Path | os.PathLike) -> Image: return cast(Image, super().from_path(path))

class Pdf(Content[PdfMimeTypes]):
    _Content_TYPE: str = "pdf"
    def __init__(self, data: bytes | str, mime_type: PdfMimeTypes = "application/pdf", validate_base64: bool = True, _original_path: str | None = None):
        super().__init__(data, mime_type=mime_type, validate_base64=validate_base64, _original_path=_original_path)
    @classmethod
    def from_data(cls, data: str | bytes, mime_type: str = "application/pdf") -> Pdf: return cast(Pdf, super().from_data(data, mime_type))
    @classmethod
    def from_path(cls, path: str | Path | os.PathLike) -> Pdf: return cast(Pdf, super().from_path(path))

class Json(Content[JsonMimeTypes]):
    _Content_TYPE: str = "json"
    def __init__(self, data: bytes | str, mime_type: JsonMimeTypes = "application/json", validate_base64: bool = True, _original_path: str | None = None):
        super().__init__(data, mime_type=mime_type, validate_base64=validate_base64, _original_path=_original_path)
    @classmethod
    def from_data(cls, data: str | bytes, mime_type: str = "application/json") -> Json: return cast(Json, super().from_data(data, mime_type))
    @classmethod
    def from_path(cls, path: str | Path | os.PathLike) -> Json: return cast(Json, super().from_path(path))

class Yaml(Content[YamlMimeTypes]):
    _Content_TYPE: str = "yaml"
    def __init__(self, data: bytes | str, mime_type: YamlMimeTypes = "application/yaml", validate_base64: bool = True, _original_path: str | None = None):
        super().__init__(data, mime_type=mime_type, validate_base64=validate_base64, _original_path=_original_path)
    @classmethod
    def from_data(cls, data: str | bytes, mime_type: str = "application/yaml") -> Yaml: return cast(Yaml, super().from_data(data, mime_type))
    @classmethod
    def from_path(cls, path: str | Path | os.PathLike) -> Yaml: return cast(Yaml, super().from_path(path))

class Csv(Content[CsvMimeTypes]):
    _Content_TYPE: str = "csv"
    def __init__(self, data: bytes | str, mime_type: CsvMimeTypes = "text/csv", validate_base64: bool = True, _original_path: str | None = None):
        super().__init__(data, mime_type=mime_type, validate_base64=validate_base64, _original_path=_original_path)
    @classmethod
    def from_data(cls, data: str | bytes, mime_type: str = "text/csv") -> Csv: return cast(Csv, super().from_data(data, mime_type))
    @classmethod
    def from_path(cls, path: str | Path | os.PathLike) -> Csv: return cast(Csv, super().from_path(path))

class Markdown(Content[MarkdownMimeTypes]):
    _Content_TYPE: str = "markdown"
    def __init__(self, data: bytes | str, mime_type: MarkdownMimeTypes = "text/markdown", validate_base64: bool = True, _original_path: str | None = None):
        super().__init__(data, mime_type=mime_type, validate_base64=validate_base64, _original_path=_original_path)
    @classmethod
    def from_data(cls, data: str | bytes, mime_type: str = "text/markdown") -> Markdown: return cast(Markdown, super().from_data(data, mime_type))
    @classmethod
    def from_path(cls, path: str | Path | os.PathLike) -> Markdown: return cast(Markdown, super().from_path(path))

class PlainText(Content[PlainTextMimeTypes]):
    _Content_TYPE: str = "plaintext"
    def __init__(self, data: bytes | str, mime_type: PlainTextMimeTypes = "text/plain", validate_base64: bool = True, _original_path: str | None = None):
        super().__init__(data, mime_type=mime_type, validate_base64=validate_base64, _original_path=_original_path)
    @classmethod
    def from_data(cls, data: str | bytes, mime_type: str = "text/plain") -> PlainText: return cast(PlainText, super().from_data(data, mime_type))
    @classmethod
    def from_path(cls, path: str | Path | os.PathLike) -> PlainText: return cast(PlainText, super().from_path(path))

class Python(Content[PythonMimeTypes]):
    _Content_TYPE: str = "python"
    def __init__(self, data: bytes | str, mime_type: PythonMimeTypes = "text/x-python", validate_base64: bool = True, _original_path: str | None = None):
        super().__init__(data, mime_type=mime_type, validate_base64=validate_base64, _original_path=_original_path)
    @classmethod
    def from_data(cls, data: str | bytes, mime_type: str = "text/x-python") -> Python: return cast(Python, super().from_data(data, mime_type))
    @classmethod
    def from_path(cls, path: str | Path | os.PathLike) -> Python: return cast(Python, super().from_path(path))

class JavaScript(Content[JavaScriptMimeTypes]):
    _Content_TYPE: str = "javascript"
    def __init__(self, data: bytes | str, mime_type: JavaScriptMimeTypes = "application/javascript", validate_base64: bool = True, _original_path: str | None = None):
        super().__init__(data, mime_type=mime_type, validate_base64=validate_base64, _original_path=_original_path)
    @classmethod
    def from_data(cls, data: str | bytes, mime_type: str = "application/javascript") -> JavaScript: return cast(JavaScript, super().from_data(data, mime_type))
    @classmethod
    def from_path(cls, path: str | Path | os.PathLike) -> JavaScript: return cast(JavaScript, super().from_path(path))

class TypeScript(Content[TypeScriptMimeTypes]):
    _Content_TYPE: str = "typescript"
    def __init__(self, data: bytes | str, mime_type: TypeScriptMimeTypes = "text/x-typescript", validate_base64: bool = True, _original_path: str | None = None):
        super().__init__(data, mime_type=mime_type, validate_base64=validate_base64, _original_path=_original_path)
    @classmethod
    def from_data(cls, data: str | bytes, mime_type: str = "text/x-typescript") -> TypeScript: return cast(TypeScript, super().from_data(data, mime_type))
    @classmethod
    def from_path(cls, path: str | Path | os.PathLike) -> TypeScript: return cast(TypeScript, super().from_path(path))

# Aliases for convenience

