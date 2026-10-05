"""Canonical location is ``weave.shared.common_interface``. This module is that module."""

import sys

from weave.shared import common_interface as _canonical
from weave.shared.common_interface import *  # noqa: F403

sys.modules[__name__] = _canonical
