"""Canonical location is ``weave.shared.sensitive_data.policy``. This module is that module."""

import sys
import warnings

from weave.shared.sensitive_data import policy as _canonical
from weave.shared.sensitive_data.policy import *  # noqa: F403

# TODO: delete this alias after weave 0.53.13.
warnings.warn(
    "weave.trace_server.sensitive_data.policy is deprecated since weave 0.53.13 "
    "and will be removed after weave 0.53.13; import "
    "weave.shared.sensitive_data.policy instead.",
    FutureWarning,
    stacklevel=2,
)

sys.modules[__name__] = _canonical
