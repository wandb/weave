"""Canonical location is ``weave.shared.tracing``. This module is that module."""

import sys
import warnings

from weave.shared import tracing as _canonical
from weave.shared.tracing import *  # noqa: F403

# TODO: delete this alias after weave 0.53.13.
warnings.warn(
    "weave.trace_server.tracing is deprecated since weave 0.53.13 and will be "
    "removed after weave 0.53.13; import weave.shared.tracing instead.",
    FutureWarning,
    stacklevel=2,
)

sys.modules[__name__] = _canonical
