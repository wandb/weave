"""Canonical location is ``weave.shared.agents.constants``. This module is that module."""

import sys

from weave.shared.agents import constants as _canonical
from weave.shared.agents.constants import *  # noqa: F403

sys.modules[__name__] = _canonical
