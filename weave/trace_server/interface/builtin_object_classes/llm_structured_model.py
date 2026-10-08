"""Canonical location is ``weave.flow.llm_structured_model``. This module is that module."""

import sys

from weave.flow import llm_structured_model as _canonical
from weave.flow.llm_structured_model import *  # noqa: F403

sys.modules[__name__] = _canonical
