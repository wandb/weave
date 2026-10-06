"""Canonical location is ``weave.shared.trace_server_interface``. This module is that module."""

import sys

from weave.shared import trace_server_interface as _canonical
from weave.shared.trace_server_interface import *  # noqa: F403

sys.modules[__name__] = _canonical
