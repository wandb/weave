"""Canonical location is ``weave.trace.trace_server_converter``. This module is that module."""

import sys
import warnings

from weave.trace import trace_server_converter as _canonical
from weave.trace.trace_server_converter import *  # noqa: F403

# TODO: delete this alias together with weave.shared.
warnings.warn(
    "weave.shared.trace_server_converter is deprecated and will be removed in a"
    " future release; import weave.trace.trace_server_converter instead.",
    FutureWarning,
    stacklevel=2,
)

sys.modules[__name__] = _canonical
