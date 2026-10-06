"""Canonical location is ``weave.shared.helpers.url_safety``. This module is that module."""

import sys

from weave.shared.helpers import url_safety as _canonical
from weave.shared.helpers.url_safety import *  # noqa: F403

sys.modules[__name__] = _canonical
