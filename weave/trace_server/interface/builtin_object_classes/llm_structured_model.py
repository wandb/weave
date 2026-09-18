"""Canonical location is ``weave.shared.interface.builtin_object_classes.llm_structured_model``. This module is that module."""

import sys

from weave.shared.interface.builtin_object_classes import (
    llm_structured_model as _canonical,
)
from weave.shared.interface.builtin_object_classes.llm_structured_model import *  # noqa: F403

sys.modules[__name__] = _canonical
