from typing import TYPE_CHECKING, Any

from weave.trace.env import is_mtsaas
from weave.trace.serialization import serializer

INLINE_MARKDOWN_THRESHOLD = 1024

if TYPE_CHECKING:
    from weave.trace.serialization.mem_artifact import MemTraceFilesArtifact

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


def save(
    obj: Markdown, artifact: "MemTraceFilesArtifact", name: str
) -> dict[str, Any] | None:
    """Save markdown content as file, return metadata."""
    use_file = len(obj.markup) >= INLINE_MARKDOWN_THRESHOLD

    # We only use files for markdown on MTSAAS for now (until the new UI is rolled out to all customers)
    use_file = use_file and is_mtsaas()

    result = {}

    if use_file:
        with artifact.new_file("markup.md", binary=False) as f:
            f.write(obj.markup)
    else:
        result["markup"] = obj.markup

    # Return metadata if present
    if obj.code_theme:
        result["code_theme"] = obj.code_theme

    if result:
        return result
    return None


def load(artifact: "MemTraceFilesArtifact", name: str, val: Any) -> Markdown:
    """Load markdown from file and metadata."""
    if "markup" in val:
        markup = val["markup"]
    else:
        with artifact.open("markup.md", binary=False) as f:
            markup = f.read()

    kwargs = {}
    if val and isinstance(val, dict) and "code_theme" in val:
        kwargs["code_theme"] = val["code_theme"]

    return Markdown(markup=markup, **kwargs)


def register() -> None:
    serializer.register_serializer(Markdown, save, load)
