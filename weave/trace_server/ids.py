"""Canonical location is ``weave.utils.ids``. This module re-exports it."""

import warnings

from weave.utils.ids import generate_id

__all__ = ["generate_id"]

# TODO: delete this alias together with weave.shared.
warnings.warn(
    "weave.trace_server.ids is deprecated since weave 0.53.13 and will be removed "
    "in a future release; import weave.utils.ids instead.",
    FutureWarning,
    stacklevel=2,
)
