"""Canonical location is ``weave.shared.service_interface``. This module is that module."""

import sys
import warnings

# weave.shared.service_interface warns too; one warning, this module's, is enough.
with warnings.catch_warnings():
    warnings.simplefilter("ignore", FutureWarning)
    from weave.shared import service_interface as _canonical
    from weave.shared.service_interface import *  # noqa: F403

# TODO: delete this alias together with weave.shared.
warnings.warn(
    "weave.trace_server.service_interface is deprecated since weave 0.53.13 and "
    "will be removed in a future release.",
    FutureWarning,
    stacklevel=2,
)

sys.modules[__name__] = _canonical
