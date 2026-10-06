"""Canonical location is ``weave.shared.sensitive_data.policy``. This module is that module."""

import sys

from weave.shared.sensitive_data import policy as _canonical
from weave.shared.sensitive_data.policy import *  # noqa: F403

sys.modules[__name__] = _canonical
