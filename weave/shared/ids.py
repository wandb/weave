"""Canonical location is ``weave.utils.ids``. This module is that module."""

import sys
import warnings

from weave.utils import ids as _canonical
from weave.utils.ids import *  # noqa: F403

# TODO: delete this alias together with weave.shared.
warnings.warn(
    "weave.shared.ids is deprecated and will be removed in a future release; "
    "import weave.utils.ids instead.",
    FutureWarning,
    stacklevel=2,
)

sys.modules[__name__] = _canonical
