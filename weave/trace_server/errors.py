"""Canonical location is ``weave.shared.errors``. This module is that module."""

import sys

from weave.shared import errors as _canonical

sys.modules[__name__] = _canonical
