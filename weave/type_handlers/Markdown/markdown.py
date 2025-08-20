from typing import TypedDict

from rich.markdown import Markdown
from typing_extensions import NotRequired

from weave.trace.serialization import serializer


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
