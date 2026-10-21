"""Canonical location is ``weave.trace.otel_span_attrs``. This module is that module."""

import sys
import warnings

from weave.trace import otel_span_attrs as _canonical
from weave.trace.otel_span_attrs import *  # noqa: F403

# TODO: delete this alias together with weave.shared.
warnings.warn(
    "weave.shared.otel_span_attrs is deprecated and will be removed in a future"
    " release; import weave.trace.otel_span_attrs instead.",
    FutureWarning,
    stacklevel=2,
)

sys.modules[__name__] = _canonical
