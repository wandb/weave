"""Canonical location is ``weave.shared.errors``. This module is that module."""

import sys
import warnings

# weave.shared.errors warns too; one warning, this module's, is enough.
with warnings.catch_warnings():
    warnings.simplefilter("ignore", FutureWarning)
    from weave.shared import errors as _canonical
    from weave.shared.errors import *  # noqa: F403

# TODO: delete this alias together with weave.shared.
warnings.warn(
    "weave.trace_server.errors is deprecated since weave 0.53.13 and will be "
    "removed in a future release; import the error classes from weave.trace.errors "
    "instead.",
    FutureWarning,
    stacklevel=2,
)

sys.modules[__name__] = _canonical
