"""Canonical location is ``weave.shared.agents.semconv``. This module is that module."""

import sys
import warnings

from weave.shared.agents import semconv as _canonical
from weave.shared.agents.semconv import *  # noqa: F403

# TODO: delete this alias after weave 0.53.13.
warnings.warn(
    "weave.trace_server.agents.semconv is deprecated since weave 0.53.13 and will "
    "be removed after weave 0.53.13; import weave.shared.agents.semconv instead.",
    FutureWarning,
    stacklevel=2,
)

sys.modules[__name__] = _canonical
