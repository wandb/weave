"""Canonical location is ``weave.shared.validation``. This module is that module."""

import sys
import warnings

from weave.shared import validation as _canonical
from weave.shared.validation import *  # noqa: F403

# TODO: delete this alias after weave 0.53.13.
warnings.warn(
    "weave.trace_server.validation is deprecated since weave 0.53.13 and will be "
    "removed after weave 0.53.13; import weave.shared.validation instead.",
    FutureWarning,
    stacklevel=2,
)

sys.modules[__name__] = _canonical
