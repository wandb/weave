"""Canonical location is ``weave.shared.validation_util``. This module is that module."""

import sys
import warnings

# weave.shared.validation_util warns too; one warning, this module's, is enough.
with warnings.catch_warnings():
    warnings.simplefilter("ignore", FutureWarning)
    from weave.shared import validation_util as _canonical
    from weave.shared.validation_util import *  # noqa: F403

# TODO: delete this alias together with weave.shared.
warnings.warn(
    "weave.trace_server.validation_util is deprecated since weave 0.53.13 and "
    "will be removed in a future release.",
    FutureWarning,
    stacklevel=2,
)

sys.modules[__name__] = _canonical
