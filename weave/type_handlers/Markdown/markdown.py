from typing import Any

from rich.markdown import Markdown

from weave.trace.serialization import serializer


def save(obj: Markdown) -> dict[str, Any]:
    # TODO: Serialize "justify" and "hyperlinks" attributes?
    d = {
        "markup": obj.markup,
    }
    if obj.code_theme:
        d["code_theme"] = obj.code_theme
    return d


def load(encoded: dict[str, Any]) -> Markdown:
    return Markdown(**encoded)


def register() -> None:
    serializer.register_serializer(Markdown, save, load)
