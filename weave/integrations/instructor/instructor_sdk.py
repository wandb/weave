from __future__ import annotations

import importlib

from weave.integrations.patcher import MultiPatcher, NoOpPatcher, SymbolPatcher
from weave.trace.autopatch import IntegrationSettings

from .instructor_iterable_utils import instructor_wrapper_async, instructor_wrapper_sync
from .instructor_partial_utils import instructor_wrapper_partial

_instructor_patcher: MultiPatcher | None = None


def get_instructor_patcher(
    settings: IntegrationSettings | None = None,
) -> MultiPatcher | NoOpPatcher:
    if settings is None:
        settings = IntegrationSettings()

    if not settings.enabled:
        return NoOpPatcher()

    global _instructor_patcher
    if _instructor_patcher is not None:
        return _instructor_patcher

    base = settings.op_settings

    create_settings = base.model_copy(update={"name": base.name or "Instructor.create"})
    async_create_settings = base.model_copy(
        update={"name": base.name or "AsyncInstructor.create"}
    )
    create_partial_settings = base.model_copy(
        update={"name": base.name or "Instructor.create_partial"}
    )
    async_create_partial_settings = base.model_copy(
        update={"name": base.name or "AsyncInstructor.create_partial"}
    )
    create_completion_settings = base.model_copy(
        update={"name": base.name or "Instructor.create_with_completion"}
    )

    _instructor_patcher = MultiPatcher(
        [
            SymbolPatcher(
                lambda: importlib.import_module("instructor.client"),
                "Instructor.create",
                instructor_wrapper_sync(create_settings),
            ),
            SymbolPatcher(
                lambda: importlib.import_module("instructor.client"),
                "Instructor.create_with_completion",
                instructor_wrapper_sync(create_completion_settings),
            ),
            SymbolPatcher(
                lambda: importlib.import_module("instructor.client"),
                "AsyncInstructor.create",
                instructor_wrapper_async(async_create_settings),
            ),
            SymbolPatcher(
                lambda: importlib.import_module("instructor.client"),
                "Instructor.create_partial",
                instructor_wrapper_partial(create_partial_settings),
            ),
            SymbolPatcher(
                lambda: importlib.import_module("instructor.client"),
                "AsyncInstructor.create_partial",
                instructor_wrapper_partial(async_create_partial_settings),
            ),
        ]
    )

    return _instructor_patcher
