"""Canonical location is ``weave.shared.interface.query``. This module is that module."""

import sys

from weave.shared.interface import query as _canonical
from weave.shared.interface.query import *  # noqa: F403

sys.modules[__name__] = _canonical
