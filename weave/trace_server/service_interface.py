"""Canonical location is ``weave.shared.service_interface``. This module is that module."""

import sys

from weave.shared import service_interface as _canonical
from weave.shared.service_interface import *  # noqa: F403

sys.modules[__name__] = _canonical
