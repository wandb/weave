"""Canonical location is ``weave.shared.validation``. This module is that module."""

import sys
import warnings

# weave.shared.validation warns too; one warning, this module's, is enough.
with warnings.catch_warnings():
    warnings.simplefilter("ignore", FutureWarning)
    from weave.shared import validation as _canonical
    from weave.shared.validation import *  # noqa: F403

# TODO: delete this alias together with weave.shared.
warnings.warn(
    "weave.trace_server.validation is deprecated since weave 0.53.13 and will be "
    "removed in a future release.",
    FutureWarning,
    stacklevel=2,
)

sys.modules[__name__] = _canonical
