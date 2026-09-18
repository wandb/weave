"""Canonical location is ``weave.shared.interface.query``. This module is that module."""

import sys

from weave.shared.interface import query as _canonical

sys.modules[__name__] = _canonical
