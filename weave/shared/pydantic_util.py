"""Canonical location is ``weave.utils.pydantic_util``. This module is that module."""

import sys
import warnings

from weave.utils import pydantic_util as _canonical
from weave.utils.pydantic_util import *  # noqa: F403

# TODO: delete this alias together with weave.shared.
warnings.warn(
    "weave.shared.pydantic_util is deprecated and will be removed in a future "
    "release; import weave.utils.pydantic_util instead.",
    FutureWarning,
    stacklevel=2,
)

sys.modules[__name__] = _canonical
