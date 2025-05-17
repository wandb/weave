from __future__ import annotations

import base64
import binascii
import json
import os
from pathlib import Path
from typing import (
    Generic,
    Optional,  # Added for Optional parameter
    TypedDict,
    cast,
)

# --- Import from our new mime_types module ---
from weave.content_types.mime_types import (
    AudioMimeTypes,
    CsvMimeTypes,
    ImageMimeTypes,
    JavaScriptMimeTypes,
    JsonMimeTypes,
    MarkdownMimeTypes,
    MimeT,
    PdfMimeTypes,
    PlainTextMimeTypes,
    PythonMimeTypes,
    TypeScriptMimeTypes,
    VideoMimeTypes,
    YamlMimeTypes,
    get_default_extension_for_mime,
    get_supported_mime_types_for_category,
    guess_mime_type_from_buffer,  # Specifically for buffer-based guessing
    guess_mime_type_from_filename,  # Specifically for extension-based guessing
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
            return data.encode("utf-8")
    return data


class ContentMetadata(TypedDict):
    """
    A TypedDict representing the metadata associated with a Content object.
    """

    original_path: str | None
    mimetype: str
    size: int


TEXT_MEDIA_CATEGORIES = {
    "json",
    "yaml",
    "csv",
    "markdown",
    "plaintext",
    "python",
    "javascript",
    "typescript",
}

# --- Content Base Class ---
class Content(Generic[MimeT]):
    _MEDIA_TYPE: str = "_base_media"
    media_category: str
    mime_type: MimeT
    data: bytes
    _original_path: str | None = None

    def __init__(
        self,
        data: bytes | str,
        mime_type: MimeT,
        validate_base64: bool = True,
        _original_path: str | None = None,
        _expected_mime_types_list: list[str] | None = None,
    ) -> None:
        cls_media_category_key = getattr(self.__class__, "_MEDIA_TYPE", "_base_media")

        if validate_base64:
            processed_data = try_decode(data)
        elif isinstance(data, str):
            processed_data = data.encode("utf-8")
        else:
            processed_data = data

        if not processed_data:
            raise ValueError(
                f"{cls_media_category_key.capitalize()} data cannot be empty."
            )

        self.data = processed_data
        self.media_category = cls_media_category_key
        self._original_path = _original_path

        current_expected_mime_types = (
            _expected_mime_types_list
            or get_supported_mime_types_for_category(self.media_category)
        )

        if not current_expected_mime_types:
            raise ValueError(
                f"No supported MIME types configured for media category '{self.media_category}'."
            )

        normalized_input_mime = str(mime_type).lower()
        if normalized_input_mime not in current_expected_mime_types:
            raise ValueError(
                f"Unsupported MIME type '{mime_type}' for {self.media_category} ({self.__class__.__name__}). "
                f"Supported MIME types are: {', '.join(current_expected_mime_types)}"
            )
        self.mime_type = mime_type

    @property
    def metadata(self) -> ContentMetadata:
        return ContentMetadata(
            original_path=self._original_path,
            mimetype=str(self.mime_type),
            size=len(self.data),
        )

    @property
    def resolved_filename(self) -> ContentMetadata:
        return ContentMetadata(
            original_path=self._original_path,
            mimetype=str(self.mime_type),
            size=len(self.data),
        )

    def export_metadata(self, path: str | Path | os.PathLike) -> str:
        path_str = os.fspath(path)
        metadata_to_export = self.metadata
        dir_name = os.path.dirname(path_str)
        if dir_name:
            os.makedirs(dir_name, exist_ok=True)
        with open(path_str, "w", encoding="utf-8") as f:
            json.dump(metadata_to_export, f, indent=4)
        return os.path.abspath(path_str)

    @classmethod
    def _get_cls_media_category_key(cls) -> str:
        category_key = getattr(cls, "_MEDIA_TYPE", "_base_media")
        if category_key == "_base_media" or not category_key:
            raise TypeError(
                f"Class {cls.__name__} must define a `_MEDIA_TYPE` category key."
            )
        return category_key

    @classmethod
    def from_data(
        cls: type[Content[MimeT]],
        data: bytes | str,
        mime_type_or_extension: Optional[str] = None,  # Parameter changed
    ) -> Content[MimeT]:
        """
        Creates a content object from raw or base64 encoded data.
        The mime_type_or_extension can be a full MIME type string, a file extension,
        or None (to guess from buffer).
        """
        cls_media_category = cls._get_cls_media_category_key()
        supported_mime_types = get_supported_mime_types_for_category(cls_media_category)

        # Ensure data is bytes for buffer guessing, if needed.
        # The __init__ will ultimately handle final conversion of input `data`.
        if isinstance(data, str):
            data = data.encode("utf-8")

        if mime_type_or_extension and mime_type_or_extension.find('/') == -1:
            # Got extension, try to get mime_type from it
            mime_type_or_extension = guess_mime_type_from_filename(f"example.{mime_type_or_extension}")

        # Use the provided or resolved mime-type if we have it
        mime_type = mime_type_or_extension or guess_mime_type_from_buffer(data)

        if mime_type is None:
            raise ValueError(
                "MIME type could not be determined from buffer and no MIME type or extension was provided.")

        mime_type_lower = mime_type.lower()
        if not mime_type_lower in supported_mime_types:
            raise ValueError(
                f"Determined MIME type '{mime_type_lower}'"
                f"is not supported for {cls_media_category} ({cls.__name__})."
                f"Supported are: {', '.join(supported_mime_types)}"
            )

        return cls(
            data=data,
            mime_type=cast(MimeT, mime_type_lower),
            validate_base64=True,
            _original_path=None,
            _expected_mime_types_list=supported_mime_types,
        )

    @classmethod
    def from_path(
        cls: type[Content[MimeT]],
        path: str | Path | os.PathLike,
    ) -> Content[MimeT]:
        cls_media_category = cls._get_cls_media_category_key()
        supported_mime_types = get_supported_mime_types_for_category(cls_media_category)
        path_str = os.fspath(path)

        if not os.path.exists(path_str):
            raise FileNotFoundError(f"File not found at path: {path_str}")

        data = open(path_str, "rb").read()

        def is_valid_mime(mime: str | None) -> bool:
            return mime is not None and mime.lower() in supported_mime_types

        # Always use filename-based guessing first
        mime_type = guess_mime_type_from_filename(path_str)

        # Could be a user defined extension but valid data
        if not is_valid_mime(mime_type):
            mime_type = guess_mime_type_from_buffer(data)

        return cls(
            data=data,
            mime_type=cast(MimeT, mime_type),
            validate_base64=False,
            _original_path=path_str,
            _expected_mime_types_list=supported_mime_types,
        )

    def export(self, path: str | Path | os.PathLike) -> str:
        path_str = os.fspath(path)
        output_ext_from_path = get_extension_from_filename(path_str)
        expected_ext_for_mime = get_default_extension_for_mime(self.mime_type)

        final_path_str = path_str
        if not output_ext_from_path and expected_ext_for_mime:
            final_path_str += expected_ext_for_mime

        with open(final_path_str, "wb") as f:
            f.write(self.data)
        return final_path_str

    def __repr__(self) -> str:
        return self.__class__.__name__

# --- Thin Wrapper Classes (Updated from_data signatures) ---
class Audio(Content[AudioMimeTypes]):
    _MEDIA_TYPE: str = "audio"

    def __init__(
        self,
        data: bytes | str,
        mime_type: AudioMimeTypes,
        validate_base64: bool = True,
        _original_path: str | None = None,
        _expected_mime_types_list: list[str] | None = None,
    ):
        super().__init__(
            data,
            mime_type=mime_type,
            validate_base64=validate_base64,
            _original_path=_original_path,
            _expected_mime_types_list=_expected_mime_types_list,
        )

    @classmethod
    def from_data(
        cls, data: str | bytes, mime_type_or_extension: Optional[str] = None
    ) -> Audio:
        return cast(Audio, super().from_data(data, mime_type_or_extension))

    @classmethod
    def from_path(cls, path: str | Path | os.PathLike) -> Audio:
        return cast(Audio, super().from_path(path))


class Video(Content[VideoMimeTypes]):
    _MEDIA_TYPE: str = "video"

    def __init__(
        self,
        data: bytes | str,
        mime_type: VideoMimeTypes,
        validate_base64: bool = True,
        _original_path: str | None = None,
        _expected_mime_types_list: list[str] | None = None,
    ):
        super().__init__(
            data,
            mime_type=mime_type,
            validate_base64=validate_base64,
            _original_path=_original_path,
            _expected_mime_types_list=_expected_mime_types_list,
        )

    @classmethod
    def from_data(
        cls, data: str | bytes, mime_type_or_extension: Optional[str] = None
    ) -> Video:
        return cast(Video, super().from_data(data, mime_type_or_extension))

    @classmethod
    def from_path(cls, path: str | Path | os.PathLike) -> Video:
        return cast(Video, super().from_path(path))


class Image(Content[ImageMimeTypes]):
    _MEDIA_TYPE: str = "image"

    def __init__(
        self,
        data: bytes | str,
        mime_type: ImageMimeTypes,
        validate_base64: bool = True,
        _original_path: str | None = None,
        _expected_mime_types_list: list[str] | None = None,
    ):
        super().__init__(
            data,
            mime_type=mime_type,
            validate_base64=validate_base64,
            _original_path=_original_path,
            _expected_mime_types_list=_expected_mime_types_list,
        )

    @classmethod
    def from_data(
        cls, data: str | bytes, mime_type_or_extension: Optional[str] = None
    ) -> Image:
        return cast(Image, super().from_data(data, mime_type_or_extension))

    @classmethod
    def from_path(cls, path: str | Path | os.PathLike) -> Image:
        return cast(Image, super().from_path(path))


class Pdf(Content[PdfMimeTypes]):
    _MEDIA_TYPE: str = "pdf"

    def __init__(
        self,
        data: bytes | str,
        mime_type: PdfMimeTypes = "application/pdf",
        validate_base64: bool = True,
        _original_path: str | None = None,
        _expected_mime_types_list: list[str] | None = None,
    ):
        super().__init__(
            data,
            mime_type=mime_type,
            validate_base64=validate_base64,
            _original_path=_original_path,
            _expected_mime_types_list=_expected_mime_types_list,
        )

    @classmethod
    def from_data(
        cls,
        data: str | bytes,
        mime_type_or_extension: Optional[str] = "application/pdf",
    ) -> Pdf:
        return cast(Pdf, super().from_data(data, mime_type_or_extension))

    @classmethod
    def from_path(cls, path: str | Path | os.PathLike) -> Pdf:
        return cast(Pdf, super().from_path(path))


class Json(Content[JsonMimeTypes]):
    _MEDIA_TYPE: str = "json"

    def __init__(
        self,
        data: bytes | str,
        mime_type: JsonMimeTypes = "application/json",
        validate_base64: bool = True,
        _original_path: str | None = None,
        _expected_mime_types_list: list[str] | None = None,
    ):
        super().__init__(
            data,
            mime_type=mime_type,
            validate_base64=validate_base64,
            _original_path=_original_path,
            _expected_mime_types_list=_expected_mime_types_list,
        )

    @classmethod
    def from_data(
        cls,
        data: str | bytes,
        mime_type_or_extension: Optional[str] = "application/json",
    ) -> Json:
        return cast(Json, super().from_data(data, mime_type_or_extension))

    @classmethod
    def from_path(cls, path: str | Path | os.PathLike) -> Json:
        return cast(Json, super().from_path(path))


class Yaml(Content[YamlMimeTypes]):
    _MEDIA_TYPE: str = "yaml"

    def __init__(
        self,
        data: bytes | str,
        mime_type: YamlMimeTypes = "application/yaml",
        validate_base64: bool = True,
        _original_path: str | None = None,
        _expected_mime_types_list: list[str] | None = None,
    ):
        super().__init__(
            data,
            mime_type=mime_type,
            validate_base64=validate_base64,
            _original_path=_original_path,
            _expected_mime_types_list=_expected_mime_types_list,
        )

    @classmethod
    def from_data(
        cls,
        data: str | bytes,
        mime_type_or_extension: Optional[str] = "application/yaml",
    ) -> Yaml:
        return cast(Yaml, super().from_data(data, mime_type_or_extension))

    @classmethod
    def from_path(cls, path: str | Path | os.PathLike) -> Yaml:
        return cast(Yaml, super().from_path(path))


class Csv(Content[CsvMimeTypes]):
    _MEDIA_TYPE: str = "csv"

    def __init__(
        self,
        data: bytes | str,
        mime_type: CsvMimeTypes = "text/csv",
        validate_base64: bool = True,
        _original_path: str | None = None,
        _expected_mime_types_list: list[str] | None = None,
    ):
        super().__init__(
            data,
            mime_type=mime_type,
            validate_base64=validate_base64,
            _original_path=_original_path,
            _expected_mime_types_list=_expected_mime_types_list,
        )

    @classmethod
    def from_data(
        cls, data: str | bytes, mime_type_or_extension: Optional[str] = "text/csv"
    ) -> Csv:
        return cast(Csv, super().from_data(data, mime_type_or_extension))

    @classmethod
    def from_path(cls, path: str | Path | os.PathLike) -> Csv:
        return cast(Csv, super().from_path(path))


class Markdown(Content[MarkdownMimeTypes]):
    _MEDIA_TYPE: str = "markdown"

    def __init__(
        self,
        data: bytes | str,
        mime_type: MarkdownMimeTypes = "text/markdown",
        validate_base64: bool = True,
        _original_path: str | None = None,
        _expected_mime_types_list: list[str] | None = None,
    ):
        super().__init__(
            data,
            mime_type=mime_type,
            validate_base64=validate_base64,
            _original_path=_original_path,
            _expected_mime_types_list=_expected_mime_types_list,
        )

    @classmethod
    def from_data(
        cls, data: str | bytes, mime_type_or_extension: Optional[str] = "text/markdown"
    ) -> Markdown:
        return cast(Markdown, super().from_data(data, mime_type_or_extension))

    @classmethod
    def from_path(cls, path: str | Path | os.PathLike) -> Markdown:
        return cast(Markdown, super().from_path(path))


class PlainText(Content[PlainTextMimeTypes]):
    _MEDIA_TYPE: str = "plaintext"

    def __init__(
        self,
        data: bytes | str,
        mime_type: PlainTextMimeTypes = "text/plain",
        validate_base64: bool = True,
        _original_path: str | None = None,
        _expected_mime_types_list: list[str] | None = None,
    ):
        super().__init__(
            data,
            mime_type=mime_type,
            validate_base64=validate_base64,
            _original_path=_original_path,
            _expected_mime_types_list=_expected_mime_types_list,
        )

    @classmethod
    def from_data(
        cls, data: str | bytes, mime_type_or_extension: Optional[str] = "text/plain"
    ) -> PlainText:
        return cast(PlainText, super().from_data(data, mime_type_or_extension))

    @classmethod
    def from_path(cls, path: str | Path | os.PathLike) -> PlainText:
        return cast(PlainText, super().from_path(path))


class Python(Content[PythonMimeTypes]):
    _MEDIA_TYPE: str = "python"

    def __init__(
        self,
        data: bytes | str,
        mime_type: PythonMimeTypes = "text/x-python",
        validate_base64: bool = True,
        _original_path: str | None = None,
        _expected_mime_types_list: list[str] | None = None,
    ):
        super().__init__(
            data,
            mime_type=mime_type,
            validate_base64=validate_base64,
            _original_path=_original_path,
            _expected_mime_types_list=_expected_mime_types_list,
        )

    @classmethod
    def from_data(
        cls, data: str | bytes, mime_type_or_extension: Optional[str] = "text/x-python"
    ) -> Python:
        return cast(Python, super().from_data(data, mime_type_or_extension))

    @classmethod
    def from_path(cls, path: str | Path | os.PathLike) -> Python:
        return cast(Python, super().from_path(path))


class JavaScript(Content[JavaScriptMimeTypes]):
    _MEDIA_TYPE: str = "javascript"

    def __init__(
        self,
        data: bytes | str,
        mime_type: JavaScriptMimeTypes = "application/javascript",
        validate_base64: bool = True,
        _original_path: str | None = None,
        _expected_mime_types_list: list[str] | None = None,
    ):
        super().__init__(
            data,
            mime_type=mime_type,
            validate_base64=validate_base64,
            _original_path=_original_path,
            _expected_mime_types_list=_expected_mime_types_list,
        )

    @classmethod
    def from_data(
        cls,
        data: str | bytes,
        mime_type_or_extension: Optional[str] = "application/javascript",
    ) -> JavaScript:
        return cast(JavaScript, super().from_data(data, mime_type_or_extension))

    @classmethod
    def from_path(cls, path: str | Path | os.PathLike) -> JavaScript:
        return cast(JavaScript, super().from_path(path))


class TypeScript(Content[TypeScriptMimeTypes]):
    _MEDIA_TYPE: str = "typescript"

    def __init__(
        self,
        data: bytes | str,
        mime_type: TypeScriptMimeTypes = "text/x-typescript",
        validate_base64: bool = True,
        _original_path: str | None = None,
        _expected_mime_types_list: list[str] | None = None,
    ):
        super().__init__(
            data,
            mime_type=mime_type,
            validate_base64=validate_base64,
            _original_path=_original_path,
            _expected_mime_types_list=_expected_mime_types_list,
        )

    @classmethod
    def from_data(
        cls,
        data: str | bytes,
        mime_type_or_extension: Optional[str] = "text/x-typescript",
    ) -> TypeScript:
        return cast(TypeScript, super().from_data(data, mime_type_or_extension))

    @classmethod
    def from_path(cls, path: str | Path | os.PathLike) -> TypeScript:
        return cast(TypeScript, super().from_path(path))

# (Example main_content_test function would go here if needed for testing)
