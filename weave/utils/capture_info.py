"""Shared client/system info capture — used by both @op tracer and Session SDK.

Returns ``weave.*`` metadata key/value pairs gated by
``should_capture_client_info()`` / ``should_capture_system_info()``. Call
sites apply their own key prefix (``"weave."`` dotted vs nested
``_WeaveKeyDict``), but the gating + value sources stay in one place.
"""

from __future__ import annotations

import platform
import sys

from weave.trace.settings import (
    should_capture_client_info,
    should_capture_system_info,
)
from weave.version import VERSION


def get_capture_info_items() -> list[tuple[str, str]]:
    """Return weave.* (subkey, value) pairs gated by capture-info settings.

    Subkeys are unprefixed (``client_version``, not ``weave.client_version``)
    so call sites can prefix or nest as their attribute shape requires.
    """
    items: list[tuple[str, str]] = []
    if should_capture_client_info():
        items.extend(
            [
                ("client_version", VERSION),
                ("source", "python-sdk"),
                ("sys_version", sys.version),
            ]
        )
    if should_capture_system_info():
        items.extend(
            [
                ("os_name", platform.system()),
                ("os_version", platform.version()),
                ("os_release", platform.release()),
            ]
        )
    return items
