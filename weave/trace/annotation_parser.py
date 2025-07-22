from __future__ import annotations

import logging
import re
from inspect import Signature

from pydantic import BaseModel

logger = logging.getLogger(__name__)

CONTENT_CLASS_NAME = "weave.type_wrappers.Content.content.Content"

# Content annotation with a format specifier
# Example: "typing.Annotated[typing.Union[str, bytes], weave.type_wrappers.Content.Content.Content[typing.Literal['mp3']]]"
# Explanation:
# - r"typing\.Annotated\[": Matches the literal "typing.Annotated["
# - r"(.+?)": Group 1. Captures the base type (non-greedy match for any characters).
#            This allows capturing complex types like `typing.Union[str, bytes]`.
# - r",\s*": Matches a comma followed by optional whitespace (this comma separates base_type from the Content annotation).
# - fr"{re.escape(content_class_name)}\[": Matches the content class name followed by "[".
# - r"typing\.Literal\[": Matches "typing.Literal[".
# - r"['\"](.+?)['\"]": Group 2. Captures any literal (non-greedy).
# - r"\]\]": Matches the two closing square brackets for Literal and Content.
# - r"\]": Matches the final closing square bracket for Annotated.

PATTERN_WITH_TYPE_HINT = re.compile(
    r"typing\.Annotated\["
    r"(.+?),\s*"  # Group 1: Base type (non-greedy)
    rf"{re.escape(CONTENT_CLASS_NAME)}\["
    r"typing\.Literal\[['\"](.+?)['\"]\]"  # Group 2: Any literal, non-greedy
    r"\]"  # Closing bracket for Content[...]
    r"\]"  # Closing bracket for Annotated[...]
)

# Content annotation without a format specifier
# Example: "typing.Annotated[SomePathLikeType, <class 'weave.type_handlers.Content.content.Content'>]"
# Explanation:
# - r"typing\.Annotated\[": Matches the literal "typing.Annotated["
# - r"(.+?)": Group 1. Captures the base type (non-greedy).
# - r",\s*": Matches a comma followed by optional whitespace.
# - fr"<class '{re.escape(content_class_name)}'>": Matches the class representation.
# - r"\]": Matches the closing square bracket for Annotated.
PATTERN_WITHOUT_TYPE_HINT = re.compile(
    r"typing\.Annotated\["
    r"(.+?),\s*"  # Group 1: Base type (non-greedy)
    rf"<class '{re.escape(CONTENT_CLASS_NAME)}'>"
    r"\]"  # Closing bracket for Annotated[...]
)


class ContentAnnotation(BaseModel):
    base_type: str
    content_class: str
    raw_annotation: str
    extension: str | None = None
    mimetype: str | None = None

def try_parse_annotation_with_hint(annotation_string: str) -> ContentAnnotation | None:
    """
    The function expects the string to be of the form:
    typing.Annotated[<SomeType>, weave.type_wrappers.Content.content.Content[typing.Literal[<format>]]]

    where <format> is a supported media format such as mp3 or wav and <SomeType> is a str (optionally base64) or bytes.

    Args:
        annotation_string: The string representation of the type annotation.

    Returns:
        ContentAnnotation | None: An instance of ContentAnnotation if the parsing is successful,
    """
    match_with_format = PATTERN_WITH_TYPE_HINT.fullmatch(annotation_string)

    if not match_with_format:
        return None

    base_type = match_with_format.group(1).strip()
    type_hint = match_with_format.group(2)

    if type_hint.find("/") > -1:
        # We know it's a Mimetype if there's a '/'
        return ContentAnnotation(
            base_type=base_type,
            content_class=CONTENT_CLASS_NAME,
            mimetype=type_hint,
            raw_annotation=annotation_string,
        )

    # Pad if there's not a leading period
    elif type_hint.find(".") != 0:
        type_hint = f".{type_hint}"

    return ContentAnnotation(
        base_type=base_type,
        content_class=CONTENT_CLASS_NAME,
        extension=type_hint,
        raw_annotation=annotation_string,
    )


def try_parse_annotation_without_hint(
    annotation_string: str,
) -> ContentAnnotation | None:
    """
    The function expects the string to be of the form:
    typing.Annotated[<SomeType>, <class 'weave.type_handlers.Content.content.Content'>]

    where <SomeType> is a string or PathLike type

    Args:
        annotation_string: The string representation of the type annotation.

    Returns:
        ContentAnnotation | None: An instance of ContentAnnotation if the parsing is successful,
    """
    match_without_format = PATTERN_WITHOUT_TYPE_HINT.fullmatch(annotation_string)

    if not match_without_format:
        return None

    return ContentAnnotation(
        base_type=match_without_format.group(1).strip(),
        content_class=CONTENT_CLASS_NAME,
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
        ContentAnnotation | ContentAnnotationWithExtention | ContentAnnotationWithMimetype | None
    """
    # Try matching the pattern with format first (it's more specific)
    return try_parse_annotation_with_hint(
        annotation_string
    ) or try_parse_annotation_without_hint(annotation_string)


def parse_from_signature(sig: Signature) -> dict[str, ContentAnnotation]:
    parsed_annotations = {}

    for param_name, param in sig.parameters.items():
        if not param.annotation:
            continue

        if parse_result := param.annotation and parse_content_annotation(
            str(param.annotation)
        ):
            parsed_annotations[param_name] = parse_result

    return parsed_annotations
