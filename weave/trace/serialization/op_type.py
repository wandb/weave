from __future__ import annotations

import logging
from typing import Callable

from weave.trace import code_capture
from weave.trace.op import Op, is_op
from weave.trace.serialization import serializer
from weave.trace.serialization.mem_artifact import MemTraceFilesArtifact

logger = logging.getLogger(__name__)


def save_instance(obj: Op, artifact: MemTraceFilesArtifact, name: str) -> None:
    """Save an Op instance using code capture."""
    code_capture.save_op_code(obj, artifact, name)


def load_instance(
    artifact: MemTraceFilesArtifact,
    name: str,
) -> Op | None:
    """Load an Op instance from captured code."""
    return code_capture.load_op_code(artifact, name)


def fully_qualified_opname(wrap_fn: Callable) -> str:
    """Get the fully qualified op name for a function."""
    return code_capture.fully_qualified_opname(wrap_fn)


serializer.register_serializer(Op, save_instance, load_instance, is_op)