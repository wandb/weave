"""Canonical location is ``weave.trace.isolated_client_executor``. This module is that module."""

import sys

from weave.trace import isolated_client_executor as _canonical
from weave.trace.isolated_client_executor import *  # noqa: F403

sys.modules[__name__] = _canonical
