"""Canonical location is ``weave.shared.agents.types``. This module is that module."""

import sys

from weave.shared.agents import types as _canonical
from weave.shared.agents.types import *  # noqa: F403

sys.modules[__name__] = _canonical
