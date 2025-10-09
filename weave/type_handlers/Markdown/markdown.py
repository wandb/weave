from typing import TYPE_CHECKING, Any

from weave.trace.serialization import serializer
from weave.trace.serialization.base_serializer import WeaveSerializer

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


class MarkdownSerializer(WeaveSerializer):
    """Serializer for rich.markdown.Markdown objects.

    Stores the markdown content as a .md file and returns metadata like code_theme.
    This demonstrates the hybrid pattern: files + metadata.
    """

    @staticmethod
    def save(
        obj: Markdown, artifact: "MemTraceFilesArtifact", name: str
    ) -> dict[str, Any] | None:
        # Save the markdown content as a .md file
        with artifact.new_file("content.md", binary=False) as f:
            f.write(obj.markup)

        # Return metadata (code_theme, etc.) as the return value
        # TODO: Serialize "justify" and "hyperlinks" attributes when needed
        metadata = {}
        if obj.code_theme:
            metadata["code_theme"] = obj.code_theme

        return metadata if metadata else None

    @staticmethod
    def load(artifact: "MemTraceFilesArtifact", name: str, metadata: Any) -> Markdown:
        """Load a Markdown object from artifact and metadata.

        Args:
            artifact: The artifact containing the content.md file
            name: Name hint (unused)
            metadata: Dict with optional code_theme

        Returns:
            Markdown object with loaded content and metadata
        """
        # Load the markdown content from file
        with artifact.open("content.md", binary=False) as f:
            markup = f.read()

        # Use metadata if available
        kwargs = {}
        if metadata and isinstance(metadata, dict):
            if "code_theme" in metadata:
                kwargs["code_theme"] = metadata["code_theme"]

        return Markdown(markup=markup, **kwargs)


def register() -> None:
    serializer.register_weave_serializer(Markdown, MarkdownSerializer)
