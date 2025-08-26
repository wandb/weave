from __future__ import annotations

import sys
import warnings
from typing import Any

from weave.trace import weave_client, weave_init
from weave.trace.autopatch import AutopatchSettings
from weave.trace.display.term import configure_logger
from weave.trace.op_protocol import PostprocessInputsFunc, PostprocessOutputFunc
from weave.trace.settings import (
    UserSettings,
    parse_and_apply_settings,
    should_disable_weave,
)

_global_postprocess_inputs: PostprocessInputsFunc | None = None
_global_postprocess_output: PostprocessOutputFunc | None = None
_global_attributes: dict[str, Any] = {}


def init(
    project_name: str,
    *,
    settings: UserSettings | dict[str, Any] | None = None,
    autopatch_settings: AutopatchSettings | None = None,
    global_postprocess_inputs: PostprocessInputsFunc | None = None,
    global_postprocess_output: PostprocessOutputFunc | None = None,
    global_attributes: dict[str, Any] | None = None,
) -> weave_client.WeaveClient:
    """Initialize weave tracking, logging to a wandb project.

    Logging is initialized globally, so you do not need to keep a reference
    to the return value of init.

    Following init, calls of weave.op() decorated functions will be logged
    to the specified project.

    Args:
        project_name: The name of the Weights & Biases project to log to.
        settings: Configuration for the Weave client generally.
        autopatch_settings: Configuration for autopatch integrations, e.g. openai
        global_postprocess_inputs: A function that will be applied to all inputs of all ops.
        global_postprocess_output: A function that will be applied to all outputs of all ops.
        global_attributes: A dictionary of attributes that will be applied to all traces.

    NOTE: Global postprocessing settings are applied to all ops after each op's own
    postprocessing.  The order is always:
    1. Op-specific postprocessing
    2. Global postprocessing

    Returns:
        A Weave client.
    """
    if not project_name or not project_name.strip():
        raise ValueError("project_name must be non-empty")

    configure_logger()

    if sys.version_info < (3, 10):
        warnings.warn(
            "Python 3.9 will reach end of life in October 2025, after which weave will drop support for it.  Please upgrade to Python 3.10 or later!",
            DeprecationWarning,
            stacklevel=2,
        )

    parse_and_apply_settings(settings)

    global _global_postprocess_inputs
    global _global_postprocess_output
    global _global_attributes

    _global_postprocess_inputs = global_postprocess_inputs
    _global_postprocess_output = global_postprocess_output
    _global_attributes = global_attributes or {}

    if should_disable_weave():
        return weave_init.init_weave_disabled()

    return weave_init.init_weave(
        project_name,
        autopatch_settings=autopatch_settings,
    )
