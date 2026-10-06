"""Canonical location is ``weave.shared.agents.semconv``. This module is that module."""

import sys

from weave.shared.agents import semconv as _canonical
from weave.shared.agents.semconv import *  # noqa: F403

sys.modules[__name__] = _canonical
