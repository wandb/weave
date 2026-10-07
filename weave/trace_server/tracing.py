"""Canonical location is ``weave.shared.tracing``. This module is that module."""

import sys

from weave.shared import tracing as _canonical
from weave.shared.tracing import *  # noqa: F403

sys.modules[__name__] = _canonical
