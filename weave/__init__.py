"""The top-level functions and classes for working with Weave."""

from weave import version
from weave.trace.api import *

__version__ = version.VERSION


from weave.flow.agent import Agent as Agent
from weave.flow.agent import AgentState as AgentState
from weave.flow.dataset import Dataset
from weave.flow.eval import Evaluation, Scorer
from weave.flow.model import Model
from weave.flow.obj import Object
from weave.trace.util import Thread as Thread
from weave.trace.util import ThreadPoolExecutor as ThreadPoolExecutor

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
