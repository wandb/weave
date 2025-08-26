"""Common types for the display system."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Style:
    """Style configuration for console output.

    Used by viewers to apply styling to text output.
    """

    color: str | None = None
    bold: bool = False
    italic: bool = False
    underline: bool = False

    def to_ansi(self, text: str) -> str:
        """Apply basic ANSI codes to text (fallback for non-rich viewers)."""
        if not any([self.color, self.bold, self.italic, self.underline]):
            return text

        # Basic ANSI color mapping
        ansi_colors = {
            "red": "\033[91m",
            "green": "\033[92m",
            "yellow": "\033[93m",
            "blue": "\033[94m",
            "magenta": "\033[95m",
            "cyan": "\033[96m",
            "white": "\033[97m",
            "black": "\033[90m",
        }

        codes = []
        if self.bold:
            codes.append("\033[1m")
        if self.italic:
            codes.append("\033[3m")
        if self.underline:
            codes.append("\033[4m")
        if self.color and self.color.lower() in ansi_colors:
            codes.append(ansi_colors[self.color.lower()])

        if codes:
            return "".join(codes) + text + "\033[0m"
        return text

    def to_rich_style(self) -> str:
        """Convert to rich style string."""
        parts = []
        if self.color:
            parts.append(self.color)
        if self.bold:
            parts.append("bold")
        if self.italic:
            parts.append("italic")
        if self.underline:
            parts.append("underline")
        return " ".join(parts)
