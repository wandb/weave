from typing import TYPE_CHECKING, Any

from weave.trace.serialization import serializer

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
    with artifact.new_file("content.md", binary=False) as f:
        f.write(obj.markup)

    # Return metadata if present
    if obj.code_theme:
        return {"code_theme": obj.code_theme}
    return None


def load(artifact: "MemTraceFilesArtifact", name: str, metadata: Any) -> Markdown:
    """Load markdown from file and metadata."""
    with artifact.open("content.md", binary=False) as f:
        markup = f.read()

    kwargs = {}
    if metadata and isinstance(metadata, dict) and "code_theme" in metadata:
        kwargs["code_theme"] = metadata["code_theme"]

    return Markdown(markup=markup, **kwargs)


def register() -> None:
    serializer.register_serializer(Markdown, save, load)
