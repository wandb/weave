"""Canonical location is ``weave.shared.errors``. This module is that module."""

import sys
import warnings

from weave.shared import errors as _canonical
from weave.shared.errors import *  # noqa: F403

# TODO: delete this alias after weave 0.53.13.
warnings.warn(
    "weave.trace_server.errors is deprecated since weave 0.53.13 and will be "
    "removed after weave 0.53.13; import weave.shared.errors instead.",
    FutureWarning,
    stacklevel=2,
)

sys.modules[__name__] = _canonical
