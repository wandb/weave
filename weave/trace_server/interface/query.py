"""Canonical location is ``weave.shared.interface.query``. This module is that module."""

import sys
import warnings

from weave.shared.interface import query as _canonical
from weave.shared.interface.query import *  # noqa: F403

# TODO: delete this alias after weave 0.53.13.
warnings.warn(
    "weave.trace_server.interface.query is deprecated since weave 0.53.13 and "
    "will be removed after weave 0.53.13; import weave.shared.interface.query "
    "instead.",
    FutureWarning,
    stacklevel=2,
)

sys.modules[__name__] = _canonical
