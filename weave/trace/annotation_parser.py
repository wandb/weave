from __future__ import annotations

import re
from inspect import Signature

from pydantic import BaseModel

CONTENT_CLASS_NAME = "weave.type_wrappers.Content.content.Content"


class ContentAnnotation(BaseModel):
    base_type: str
    media_class: str
    raw_annotation: str
    type_hint: str | None = None


def parse_data_annotation(annotation_string: str) -> ContentAnnotation | None:
    """
    The function expects the string to be of the form:
    typing.Annotated[<SomeType>, weave.type_wrappers.Content.content.Content[typing.Literal[<format>]]]

    where <format> is a supported media format such as mp3 or wav and <SomeType> is a str (optionally base64) or bytes.

    Args:
        annotation_string: The string representation of the type annotation.

    Returns:
        ContentAnnotation | None: An instance of ContentAnnotation if the parsing is successful,
    """
    # Content annotation with a format specifier
    # Example: "typing.Annotated[typing.Union[str, bytes], weave.type_wrappers.Content.Content.Content[typing.Literal['mp3']]]"
    # Explanation:
    # - r"typing\.Annotated\[": Matches the literal "typing.Annotated["
    # - r"(.+?)": Group 1. Captures the base type (non-greedy match for any characters).
    #            This allows capturing complex types like `typing.Union[str, bytes]`.
    # - r",\s*": Matches a comma followed by optional whitespace (this comma separates base_type from the Content annotation).
    # - fr"{re.escape(content_class_name)}\[": Matches the content class name followed by "[".
    # - r"typing\.Literal\[": Matches "typing.Literal[".
    # - r"['\"](mp3|wav)['\"]": Group 2. Captures 'mp3' or 'wav' (allowing single or double quotes).
    # - r"\]\]": Matches the two closing square brackets for Literal and Content.
    # - r"\]": Matches the final closing square bracket for Annotated.

    pattern_with_format = re.compile(
        r"typing\.Annotated\["
        r"(.+?),\s*"  # Group 1: Base type (non-greedy)
        rf"{re.escape(CONTENT_CLASS_NAME)}\["
        r"typing\.Literal\[['\"](.+?)['\"]\]"  # Group 2: Any literal, non-greedy
        r"\]"  # Closing bracket for Content[...]
        r"\]"  # Closing bracket for Annotated[...]
    )
    match_with_format = pattern_with_format.fullmatch(annotation_string)

    if not match_with_format:
        return None

    base_type = match_with_format.group(1).strip()
    type_hint = match_with_format.group(2)
    return ContentAnnotation(
        base_type=base_type,
        media_class=CONTENT_CLASS_NAME,
        type_hint=type_hint,
        raw_annotation=annotation_string,
    )


def parse_file_annotation(annotation_string: str) -> ContentAnnotation | None:
    """
    The function expects the string to be of the form:
    typing.Annotated[<SomeType>, <class 'weave.type_handlers.Content.content.Content'>]

    where <SomeType> is a string or PathLike type

    Args:
        annotation_string: The string representation of the type annotation.

    Returns:
        ContentFileAnnotation | None: An instance of ContentFileAnnotation if the parsing is successful,
    """
    # Content annotation without a format specifier
    # Example: "typing.Annotated[SomePathLikeType, <class 'weave.type_handlers.Content.content.Content'>]"
    # Explanation:
    # - r"typing\.Annotated\[": Matches the literal "typing.Annotated["
    # - r"(.+?)": Group 1. Captures the base type (non-greedy).
    # - r",\s*": Matches a comma followed by optional whitespace.
    # - fr"<class '{re.escape(content_class_name)}'>": Matches the class representation.
    # - r"\]": Matches the closing square bracket for Annotated.
    pattern_without_format = re.compile(
        r"typing\.Annotated\["
        r"(.+?),\s*"  # Group 1: Base type (non-greedy)
        rf"<class '{re.escape(CONTENT_CLASS_NAME)}'>"
        r"\]"  # Closing bracket for Annotated[...]
    )

    match_without_format = pattern_without_format.fullmatch(annotation_string)

    if not match_without_format:
        return None

    return ContentAnnotation(
        base_type=match_without_format.group(1).strip(),
        media_class=CONTENT_CLASS_NAME,
        raw_annotation=annotation_string,
    )


def parse_content_annotation(
    annotation_string: str,
) -> ContentAnnotation | None:
    """
    Parses an content type annotation string.

    The function expects the string to be one of two forms:
    1. typing.Annotated[SomeType, weave.type_wrappers.Content.content.Content[typing.Literal['format']]]
    2. typing.Annotated[SomeType, <class 'weave.type_wrappers.Content.content.Content'>]

    It extracts the base type (which can be complex, like typing.Union),
    confirms the Content class, and identifies the content format.

    Args:
        annotation_string: The string representation of the type annotation.

    Returns:
        A dictionary containing:
        - "base_type": The underlying type being annotated (e.g., "SomeType", "str", "typing.Union[str, bytes]").
        - "content_class": The name of the content handler class.
        - "content_format": The content format ("mp3", "wav") if specified, otherwise None.
        - "raw_annotation": The original input string.
        If parsing fails, it returns a dictionary with an "error" key and "raw_annotation".
    """
    # Try matching the pattern with format first (it's more specific)
    return parse_data_annotation(annotation_string) or parse_file_annotation(
        annotation_string
    )


def parse_from_signature(sig: Signature) -> dict[str, ContentAnnotation]:
    parsed_annotations = {}

    for param_name, param in sig.parameters.items():
        if not param.annotation:
            continue

        parse_result = parse_content_annotation(str(param.annotation))

        if not parse_result:
            continue

        parsed_annotations[param_name] = parse_result

    return parsed_annotations
