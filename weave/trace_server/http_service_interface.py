"""Canonical location is ``weave.shared.http_service_interface``. This module is that module."""

import sys

from weave.shared import http_service_interface as _canonical
from weave.shared.http_service_interface import *  # noqa: F403

sys.modules[__name__] = _canonical
