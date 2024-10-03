"""The top-level functions and classes for working with Weave."""

from weave import version
from weave.flow import *
from weave.trace.api import *
from weave.trace.util import Thread, ThreadPoolExecutor  # noqa: F401

__version__ = version.VERSION


# Special object informing doc generation tooling which symbols
# to document & to associate with this module.
__docspec__ = [
    # Re-exported from trace.api
    init,
    publish,
    ref,
    require_current_call,
    get_current_call,
    finish,
    op,
    attributes,
    # Re-exported from flow module
    Object,
    Dataset,
    Model,
    Evaluation,
    Scorer,
]
