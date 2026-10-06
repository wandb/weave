"""Canonical location is ``weave.shared.validation_util``. This module is that module."""

import sys

from weave.shared import validation_util as _canonical
from weave.shared.validation_util import *  # noqa: F403

sys.modules[__name__] = _canonical
