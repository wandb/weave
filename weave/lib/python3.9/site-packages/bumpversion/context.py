"""Context for rendering messages and tags."""

import calendar
import datetime
from collections import ChainMap
from dataclasses import asdict
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:  # pragma: no-coverage
    from bumpversion.config import Config
    from bumpversion.scm import SCMInfo
    from bumpversion.versioning.models import Version

MONTH_ABBREVIATIONS = [abbr for abbr in calendar.month_abbr if abbr]

CALVER_PATTERN_MAP = {
    "{YYYY}": r"(?:[1-9][0-9]{3})",
    "{YY}": r"(?:[1-9][0-9]?)",
    "{0Y}": r"(?:[0-9]{2})",
    "{MMM}": f'(?:{"|".join(MONTH_ABBREVIATIONS)})',
    "{MM}": r"(?:1[0-2]|[1-9])",
    "{0M}": r"(?:1[0-2]|0[1-9])",
    "{DD}": r"(?:3[0-1]|[1-2][0-9]|[1-9])",
    "{0D}": r"(?:3[0-1]|[1-2][0-9]|0[1-9])",
    "{JJJ}": r"(?:36[0-6]|3[0-5][0-9]|[1-2][0-9][0-9]|[1-9][0-9]|[1-9])",
    "{00J}": r"(?:36[0-6]|3[0-5][0-9]|[1-2][0-9][0-9]|0[1-9][0-9]|00[1-9])",
    "{Q}": r"(?:[1-4])",
    "{WW}": r"(?:5[0-3]|[1-4][0-9]|[0-9])",
    "{0W}": r"(?:5[0-3]|[0-4][0-9])",
    "{UU}": r"(?:5[0-3]|[1-4][0-9]|[0-9])",
    "{0U}": r"(?:5[0-3]|[0-4][0-9])",
    "{VV}": r"(?:5[0-3]|[1-4][0-9]|[1-9])",
    "{0V}": r"(?:5[0-3]|[1-4][0-9]|0[1-9])",
    "{GGGG}": r"(?:[1-9][0-9]{3})",
    "{GG}": r"(?:[0-9][0-9]?)",
    "{0G}": r"(?:[0-9]{2})",
    "{INC0}": r"(?:[0-9]+)",
    "{INC1}": r"[1-9][0-9]*",
}


def calver_string_to_regex(calver_format: str) -> str:
    """Convert the calver format string to a regex pattern."""
    pattern = calver_format
    for key, value in CALVER_PATTERN_MAP.items():
        pattern = pattern.replace(key, value)
    return pattern


def prefixed_environ() -> dict:
    """Return a dict of the environment with keys wrapped in `${}`."""
    import os

    return {f"${key}": value for key, value in os.environ.items()}


def base_context(scm_info: Optional["SCMInfo"] = None) -> ChainMap:
    """The default context for rendering messages and tags."""
    from bumpversion.scm import SCMInfo  # Including this here to avoid circular imports

    scm = asdict(scm_info) if scm_info else asdict(SCMInfo())

    return ChainMap(
        {
            "now": datetime.datetime.now(),
            "utcnow": datetime.datetime.now(datetime.timezone.utc),
        },
        prefixed_environ(),
        scm,
        {c: c for c in ("#", ";")},
    )


def get_context(
    config: "Config", current_version: Optional["Version"] = None, new_version: Optional["Version"] = None
) -> ChainMap:
    """Return the context for rendering messages and tags."""
    ctx = base_context(config.scm_info)
    ctx = ctx.new_child({"current_version": config.current_version})
    if current_version:
        ctx = ctx.new_child({f"current_{part}": current_version[part].value for part in current_version})
    if new_version:
        ctx = ctx.new_child({f"new_{part}": new_version[part].value for part in new_version})
    return ctx


def get_datetime_info(current_dt: datetime.datetime) -> dict:
    """Return the full structure of the given datetime for formatting."""
    return {
        "YYYY": current_dt.strftime("%Y"),
        "YY": current_dt.strftime("%y").lstrip("0") or "0",
        "0Y": current_dt.strftime("%y"),
        "MMM": current_dt.strftime("%b"),
        "MM": str(current_dt.month),
        "0M": current_dt.strftime("%m"),
        "DD": str(current_dt.day),
        "0D": current_dt.strftime("%d"),
        "JJJ": current_dt.strftime("%j").lstrip("0"),
        "00J": current_dt.strftime("%j"),
        "Q": str((current_dt.month - 1) // 3 + 1),
        "WW": current_dt.strftime("%W").lstrip("0") or "0",
        "0W": current_dt.strftime("%W"),
        "UU": current_dt.strftime("%U").lstrip("0") or "0",
        "0U": current_dt.strftime("%U"),
        "VV": current_dt.strftime("%V").lstrip("0") or "0",
        "0V": current_dt.strftime("%V"),
        "GGGG": current_dt.strftime("%G"),
        "GG": current_dt.strftime("%G")[2:].lstrip("0") or "0",
        "0G": current_dt.strftime("%G")[2:],
    }
