from typing import Any, TypedDict

from typing_extensions import NotRequired

from weave.trace.serialization import serializer

# Try to import rich Markdown, but make it optional
try:
    from rich.markdown import Markdown

    RICH_MARKDOWN_AVAILABLE = True
except ImportError:
    RICH_MARKDOWN_AVAILABLE = False

    # Create a dummy Markdown class for when rich is not available
    class Markdown:  # type: ignore[no-redef]
        def __init__(self, markup: str, code_theme: str = "monokai", **kwargs: Any):
            self.markup = markup
            self.code_theme = code_theme


# TODO: Serialize "justify" and "hyperlinks" attributes?
class SerializedMarkdown(TypedDict):
    markup: str
    code_theme: NotRequired[str]


def save(obj: Markdown) -> SerializedMarkdown:
    d: SerializedMarkdown = {
        "markup": obj.markup,
    }
    if obj.code_theme:
        d["code_theme"] = obj.code_theme
    return d


def load(encoded: SerializedMarkdown) -> Markdown:
    return Markdown(**encoded)


def register() -> None:
    serializer.register_serializer(Markdown, save, load)
