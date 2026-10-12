"""Canonical location is ``weave.shared.interface.builtin_object_classes.leaderboard``. This module is that module."""

import sys
import warnings

from weave.shared.interface.builtin_object_classes import leaderboard as _canonical
from weave.shared.interface.builtin_object_classes.leaderboard import *  # noqa: F403

# TODO: delete this alias after weave 0.53.13.
warnings.warn(
    "weave.trace_server.interface.builtin_object_classes.leaderboard is "
    "deprecated since weave 0.53.13 and will be removed after weave 0.53.13; "
    "import weave.shared.interface.builtin_object_classes.leaderboard instead.",
    FutureWarning,
    stacklevel=2,
)

sys.modules[__name__] = _canonical
