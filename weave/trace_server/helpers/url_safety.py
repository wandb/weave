"""Canonical location is ``weave.utils.url_safety``. This module is that module."""

import sys
import warnings

from weave.utils import url_safety as _canonical
from weave.utils.url_safety import *  # noqa: F403

# TODO: delete this alias together with weave.shared.
warnings.warn(
    "weave.trace_server.helpers.url_safety is deprecated since weave 0.53.13 "
    "and will be removed in a future release; import weave.utils.url_safety "
    "instead.",
    FutureWarning,
    stacklevel=2,
)

sys.modules[__name__] = _canonical
