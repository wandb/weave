"""Canonical location is ``weave.shared.agents.constants``. This module is that module."""

import sys
import warnings

from weave.shared.agents import constants as _canonical
from weave.shared.agents.constants import *  # noqa: F403

# TODO: delete this alias after weave 0.53.13.
warnings.warn(
    "weave.trace_server.agents.constants is deprecated since weave 0.53.13 and "
    "will be removed after weave 0.53.13; import weave.shared.agents.constants "
    "instead.",
    FutureWarning,
    stacklevel=2,
)

sys.modules[__name__] = _canonical
