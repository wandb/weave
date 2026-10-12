"""Canonical location is ``weave.shared.trace_server_converter``. This module is that module."""

import sys
import warnings

from weave.shared import trace_server_converter as _canonical
from weave.shared.trace_server_converter import *  # noqa: F403

# TODO: delete this alias after weave 0.53.13.
warnings.warn(
    "weave.trace_server.trace_server_converter is deprecated since weave 0.53.13 "
    "and will be removed after weave 0.53.13; import "
    "weave.shared.trace_server_converter instead.",
    FutureWarning,
    stacklevel=2,
)

sys.modules[__name__] = _canonical
