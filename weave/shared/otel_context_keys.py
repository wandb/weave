"""Canonical location is ``weave.trace.otel_context_keys``. This module is that module."""

import sys
import warnings

from weave.trace import otel_context_keys as _canonical
from weave.trace.otel_context_keys import *  # noqa: F403

# TODO: delete this alias together with weave.shared.
warnings.warn(
    "weave.shared.otel_context_keys is deprecated and will be removed in a "
    "future release; import weave.trace.otel_context_keys instead.",
    FutureWarning,
    stacklevel=2,
)

sys.modules[__name__] = _canonical
