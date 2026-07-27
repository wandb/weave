"""Shared client/system info capture — used by both @op tracer and Conversation SDK.

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


def get_capture_info() -> dict[str, str]:
    """Return weave.* metadata keys (unprefixed), gated by capture-info settings.

    Keys are unprefixed (``client_version``, not ``weave.client_version``)
    so call sites can prefix or nest as their attribute shape requires.
    Both settings can independently include or exclude their key group.
    """
    info: dict[str, str] = {}
    if should_capture_client_info():
        info["client_version"] = VERSION
        info["source"] = "python-sdk"
        info["sys_version"] = sys.version
    if should_capture_system_info():
        info["os_name"] = platform.system()
        info["os_version"] = platform.version()
        info["os_release"] = platform.release()
    return info
