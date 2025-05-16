import re
from typing import Dict, Any
from pydantic import BaseModel
from inspect import Signature

AUDIO_CLASS_NAME = "weave.trace.type_wrappers.audio.Audio"

class AudioAnnotation(BaseModel):
    base_type: str
    media_class: str
    raw_annotation: str

class AudioFileAnnotation(AudioAnnotation):
    ...

class AudioDataAnnotation(AudioAnnotation):
    format: str


def parse_data_annotation(annotation_string: str) -> AudioDataAnnotation | None:
    """
    The function expects the string to be of the form:
    typing.Annotated[<SomeType>, weave.type_handlers.Audio.audio.Audio[typing.Literal[<format>]]]

    where <format> is a supported media format such as mp3 or wav and <SomeType> is a str (optionally base64) or bytes.

    Args:
        annotation_string: The string representation of the type annotation.

    Returns:
        AudioDataAnnotation | None: An instance of AudioDataAnnotation if the parsing is successful,
    """

    # Audio annotation with a format specifier
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
        fr"{re.escape(AUDIO_CLASS_NAME)}\["
        r"typing\.Literal\[['\"](mp3|wav)['\"]\]"  # Group 2: Format (mp3 or wav)
        r"\]"  # Closing bracket for Audio[...]
        r"\]"  # Closing bracket for Annotated[...]
    )

    match_with_format = pattern_with_format.fullmatch(annotation_string)
    if match_with_format:
        base_type = match_with_format.group(1).strip()
        audio_format = match_with_format.group(2)
        return AudioDataAnnotation(
            base_type=base_type,
            media_class=AUDIO_CLASS_NAME,
            format=audio_format,
            raw_annotation = annotation_string
        )



def parse_file_annotation(annotation_string: str) -> AudioFileAnnotation | None:
    """
    The function expects the string to be of the form:
    typing.Annotated[<SomeType>, <class 'weave.type_handlers.Audio.audio.Audio'>]

    where <SomeType> is a string or PathLike type

    Args:
        annotation_string: The string representation of the type annotation.

    Returns:
        AudioFileAnnotation | None: An instance of AudioFileAnnotation if the parsing is successful,
    """

    # Audio annotation without a format specifier
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
        fr"<class '{re.escape(AUDIO_CLASS_NAME)}'>"
        r"\]"  # Closing bracket for Annotated[...]
    )

    match_without_format = pattern_without_format.fullmatch(annotation_string)

    if not match_without_format:
        return

    return AudioFileAnnotation(
        base_type=match_without_format.group(1).strip(),
        media_class=AUDIO_CLASS_NAME,
        raw_annotation=annotation_string
    )
def parse_audio_annotation(annotation_string: str) -> AudioFileAnnotation | AudioDataAnnotation | None:
    """
    Parses an audio type annotation string.

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

    # Try matching the pattern with format first (it's more specific)
    return parse_data_annotation(annotation_string) or parse_file_annotation(annotation_string)

def parse_from_signature(sig: Signature) -> dict[str, AudioAnnotation]:

    parsed_annotations = {}

    for param_name, param in sig.parameters.items():
        if not param.annotation:
            continue

        parse_result = parse_audio_annotation(str(param.annotation))

        if not parse_result:
            continue

        parsed_annotations[param_name] = parse_result

    return parsed_annotations

def postprocess_input_handler(
    args: Dict[str, Any], parsed_annotations: Dict[str, AudioFileAnnotation | AudioDataAnnotation]
) -> Dict[str, Any]:
    """
    Post-processes the arguments based on the parsed annotations.
    Args:
        args: The original arguments passed to the function.
        parsed_annotations: The parsed annotations for each argument.
    Returns:
        A dictionary of processed arguments.
    """
    for param_name, annotation in parsed_annotations.items():
        if isinstance(annotation, AudioFileAnnotation):
            # Handle file-based audio
            pass
        elif isinstance(annotation, AudioDataAnnotation):
            # Handle data-based audio
            pass
    return args
