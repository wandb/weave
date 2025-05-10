import re
from typing import Dict, Any
from inspect import Signature

def parse_audio_annotation(annotation_string: str) -> Dict[str, Any]:
    """
    Parses a simplified audio type annotation string.

    The function expects the string to be one of two forms:
    1. typing.Annotated[SomeType, weave.type_handlers.Audio.audio.Audio[typing.Literal['format']]]
    2. typing.Annotated[SomeType, <class 'weave.type_handlers.Audio.audio.Audio'>]

    It extracts the base type (which can be complex, like typing.Union),
    confirms the Audio class, and identifies the audio format.

    Args:
        annotation_string: The string representation of the type annotation.

    Returns:
        A dictionary containing:
        - "base_type": The underlying type being annotated (e.g., "SomeType", "str", "typing.Union[str, bytes]").
        - "audio_class": The name of the audio handler class.
        - "audio_format": The audio format ("mp3", "wav") if specified, otherwise None.
        - "raw_annotation": The original input string.
        If parsing fails, it returns a dictionary with an "error" key and "raw_annotation".
    """
    audio_class_name = "weave.type_handlers.Audio.audio.Audio"

    # Pattern 1: Audio annotation with a format specifier
    # Example: "typing.Annotated[typing.Union[str, bytes], weave.type_handlers.Audio.audio.Audio[typing.Literal['mp3']]]"
    # Explanation:
    # - r"typing\.Annotated\[": Matches the literal "typing.Annotated["
    # - r"(.+?)": Group 1. Captures the base type (non-greedy match for any characters).
    #            This allows capturing complex types like `typing.Union[str, bytes]`.
    # - r",\s*": Matches a comma followed by optional whitespace (this comma separates base_type from the Audio annotation).
    # - fr"{re.escape(audio_class_name)}\[": Matches the audio class name followed by "[".
    # - r"typing\.Literal\[": Matches "typing.Literal[".
    # - r"['\"](mp3|wav)['\"]": Group 2. Captures 'mp3' or 'wav' (allowing single or double quotes).
    # - r"\]\]": Matches the two closing square brackets for Literal and Audio.
    # - r"\]": Matches the final closing square bracket for Annotated.
    pattern_with_format = re.compile(
        r"typing\.Annotated\["
        r"(.+?),\s*"  # Group 1: Base type (non-greedy)
        fr"{re.escape(audio_class_name)}\["
        r"typing\.Literal\[['\"](mp3|wav)['\"]\]"  # Group 2: Format (mp3 or wav)
        r"\]"  # Closing bracket for Audio[...]
        r"\]"  # Closing bracket for Annotated[...]
    )

    # Pattern 2: Audio annotation without a format specifier
    # Example: "typing.Annotated[SomePathLikeType, <class 'weave.type_handlers.Audio.audio.Audio'>]"
    # Explanation:
    # - r"typing\.Annotated\[": Matches the literal "typing.Annotated["
    # - r"(.+?)": Group 1. Captures the base type (non-greedy).
    # - r",\s*": Matches a comma followed by optional whitespace.
    # - fr"<class '{re.escape(audio_class_name)}'>": Matches the class representation.
    # - r"\]": Matches the closing square bracket for Annotated.
    pattern_without_format = re.compile(
        r"typing\.Annotated\["
        r"(.+?),\s*"  # Group 1: Base type (non-greedy)
        fr"<class '{re.escape(audio_class_name)}'>"
        r"\]"  # Closing bracket for Annotated[...]
    )

    # Try matching the pattern with format first (it's more specific)
    match_with_format = pattern_with_format.fullmatch(annotation_string)
    if match_with_format:
        base_type = match_with_format.group(1).strip()
        audio_format = match_with_format.group(2)
        return {
            "base_type": base_type,
            "audio_class": audio_class_name,
            "audio_format": audio_format,
            "raw_annotation": annotation_string
        }

    # If not matched, try matching the pattern without format
    match_without_format = pattern_without_format.fullmatch(annotation_string)
    if match_without_format:
        base_type = match_without_format.group(1).strip()
        return {
            "base_type": base_type,
            "audio_class": audio_class_name,
            "audio_format": None,  # No format specified
            "raw_annotation": annotation_string
        }

    # If neither pattern matches
    return {
        "error": "Annotation string does not match expected simplified Audio patterns.",
        "raw_annotation": annotation_string
    }

def parse_from_signature(sig: Signature):
    parsed_annotations = []
    for param_name, param in sig.parameters.items():
        print(param.annotation)
        if param.annotation:
            parse_result = parse_audio_annotation(str(param.annotation))
            if not parse_result.get("error"):
                parsed_annotations.append((param_name, parse_result))
    return parsed_annotations
