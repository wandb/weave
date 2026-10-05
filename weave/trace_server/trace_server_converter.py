"""Canonical location is ``weave.shared.trace_server_converter``. This module is that module."""

import sys

from weave.shared import trace_server_converter as _canonical
from weave.shared.trace_server_converter import *  # noqa: F403

sys.modules[__name__] = _canonical
