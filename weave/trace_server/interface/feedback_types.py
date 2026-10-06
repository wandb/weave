"""Canonical location is ``weave.shared.interface.feedback_types``. This module is that module."""

import sys

from weave.shared.interface import feedback_types as _canonical
from weave.shared.interface.feedback_types import *  # noqa: F403

sys.modules[__name__] = _canonical
