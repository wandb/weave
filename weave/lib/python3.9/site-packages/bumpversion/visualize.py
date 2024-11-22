"""Visualize the bumpversion process."""

from dataclasses import dataclass
from typing import List, Optional

from bumpversion.bump import get_next_version
from bumpversion.config import Config
from bumpversion.context import base_context, get_context
from bumpversion.exceptions import BumpVersionError
from bumpversion.ui import print_info

BOX_CHARS = {
    "ascii": ["+", "+", "+", "+", "+", "+", "+", "+", "-", "|", "+"],
    "light": ["╯", "╮", "╭", "╰", "┤", "┴", "┬", "├", "─", "│", "┼"],
}


@dataclass
class Border:
    """A border definition."""

    corner_bottom_right: str
    corner_top_right: str
    corner_top_left: str
    corner_bottom_left: str
    divider_left: str
    divider_up: str
    divider_down: str
    divider_right: str
    line: str
    pipe: str
    cross: str


def lead_string(version_str: str, border: Border, blank: bool = False) -> str:
    """
    Return the first part of a string with the bump character or spaces of the correct amount.

    Examples:
        >>> lead_string("1.0.0", Border(*BOX_CHARS["light"]))
        '1.0.0 ── bump ─'
        >>> lead_string("1.0.0", Border(*BOX_CHARS["light"]), blank=True)
        '               '

    Args:
        version_str: The string to render as the starting point
        border: The border definition to draw the lines
        blank: If `True`, return a blank string the same length as the version bump string

    Returns:
        The version bump string or a blank string
    """
    version_bump = f"{version_str} {border.line * 2} bump {border.line}"
    return " " * len(version_bump) if blank else version_bump


def connection_str(border: Border, has_next: bool = False, has_previous: bool = False) -> str:
    """
    Return the correct connection string based on the next and previous.

    Args:
        border: The border definition to draw the lines
        has_next: If `True`, there is a next line
        has_previous: If `True`, there is a previous line

    Returns:
        A string that connects left-to-right and top-to-bottom based on the next and previous
    """
    if has_next and has_previous:
        return border.divider_right + border.line
    elif has_next:
        return border.divider_down + border.line
    elif has_previous:
        return border.corner_bottom_left + border.line
    else:
        return border.line * 2


def labeled_line(label: str, border: Border, fit_length: Optional[int] = None) -> str:
    """
    Return the version part string with the correct padding.

    Args:
        label: The label to render
        border: The border definition to draw the lines
        fit_length: The length to fit the label to

    Returns:
        A labeled line with leading and trailing spaces
    """
    if fit_length is None:
        fit_length = len(label)
    return f" {label} {border.line * (fit_length - len(label))}{border.line} "


def filter_version_parts(config: Config) -> List[str]:
    """
    Return the version parts that are in the configuration.

    Args:
        config: The configuration to check against

    Returns:
        The version parts that are in the configuration
    """
    version_parts = [part for part in config.version_config.order if not part.startswith("$")]
    default_context = base_context(config.scm_info)
    return [part for part in version_parts if part not in default_context]


def visualize(config: Config, version_str: str, box_style: str = "light") -> None:
    """Output a visualization of the bump-my-version bump process."""
    version = config.version_config.parse(version_str, raise_error=True)
    version_parts = filter_version_parts(config)
    num_parts = len(version_parts)

    box_style = box_style if box_style in BOX_CHARS else "light"
    border = Border(*BOX_CHARS[box_style])

    version_lead = lead_string(version_str, border)
    blank_lead = lead_string(version_str, border, blank=True)
    version_part_length = max(len(part) for part in version_parts)
    lines = []
    for i, part in enumerate(version_parts):
        line = [version_lead] if i == 0 else [blank_lead]

        try:
            next_version = get_next_version(version, config, part, None)
            next_version_str = config.version_config.serialize(next_version, get_context(config))
        except (BumpVersionError, ValueError) as e:
            next_version_str = f"invalid: {e}"

        has_next = i < num_parts - 1
        has_previous = i > 0
        line.append(connection_str(border, has_next=has_next, has_previous=has_previous))
        line.append(labeled_line(part, border, version_part_length))
        line.append(next_version_str)
        lines.append("".join(line))
    print_info("\n".join(lines))
