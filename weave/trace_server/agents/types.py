"""Canonical location is ``weave.shared.agents.types``. This module is that module."""

import sys
import warnings

from weave.shared.agents import types as _canonical
from weave.shared.agents.types import *  # noqa: F403

# TODO: delete this alias together with weave.shared.
warnings.warn(
    "weave.trace_server.agents.types is deprecated since weave 0.53.13 and will be "
    "removed in a future release.",
    FutureWarning,
    stacklevel=2,
)

sys.modules[__name__] = _canonical
