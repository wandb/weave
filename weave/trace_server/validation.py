"""Canonical location is ``weave.shared.validation``. This module is that module."""

import sys

from weave.shared import validation as _canonical
from weave.shared.validation import *  # noqa: F403

sys.modules[__name__] = _canonical
