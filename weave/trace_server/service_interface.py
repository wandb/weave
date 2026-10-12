"""Canonical location is ``weave.shared.service_interface``. This module is that module."""

import sys
import warnings

from weave.shared import service_interface as _canonical
from weave.shared.service_interface import *  # noqa: F403

# TODO: delete this alias after weave 0.53.13.
warnings.warn(
    "weave.trace_server.service_interface is deprecated since weave 0.53.13 and "
    "will be removed after weave 0.53.13; import weave.shared.service_interface "
    "instead.",
    FutureWarning,
    stacklevel=2,
)

sys.modules[__name__] = _canonical
