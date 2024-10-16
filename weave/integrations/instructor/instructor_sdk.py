import importlib

from weave.trace.patcher import MultiPatcher, SymbolPatcher

from .instructor_iterable_utils import instructor_wrapper_async, instructor_wrapper_sync
from .instructor_partial_utils import instructor_wrapper_partial

instructor_patcher = MultiPatcher(
    [
        SymbolPatcher(
            lambda: importlib.import_module("instructor.client"),
            "Instructor.create",
            instructor_wrapper_sync(name="Instructor.create"),
        ),
        SymbolPatcher(
            lambda: importlib.import_module("instructor.client"),
            "AsyncInstructor.create",
            instructor_wrapper_async(name="AsyncInstructor.create"),
        ),
        SymbolPatcher(
            lambda: importlib.import_module("instructor.client"),
            "Instructor.create_partial",
            instructor_wrapper_partial(name="Instructor.create_partial"),
        ),
        SymbolPatcher(
            lambda: importlib.import_module("instructor.client"),
            "AsyncInstructor.create_partial",
            instructor_wrapper_partial(name="AsyncInstructor.create_partial"),
        ),
    ]
)
