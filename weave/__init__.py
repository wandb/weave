"""The top-level functions and classes for working with Weave."""

import sys
import warnings

if sys.version_info < (3, 10):  # noqa: UP036
    warnings.warn(
        "Weave only supports Python 3.10 or higher; please upgrade your Python version to avoid potential issues.",
        stacklevel=2,
    )

from weave import version
from weave.trace.api import *

__version__ = version.VERSION

from weave.integrations.wandb import wandb_init_hook

wandb_init_hook()

from weave.agent.agent import Agent as Agent
from weave.agent.agent import AgentState as AgentState
from weave.dataset.dataset import Dataset
from weave.evaluation.eval import Evaluation
from weave.evaluation.eval_imperative import EvaluationLogger
from weave.flow.annotation_spec import AnnotationSpec
from weave.flow.model import Model
from weave.flow.monitor import Monitor
from weave.flow.saved_view import SavedView
from weave.flow.scorer import Scorer
from weave.initialization import *
from weave.object.obj import Object
from weave.prompt.prompt import EasyPrompt, MessagesPrompt, Prompt, StringPrompt
from weave.trace.log_call import log_call
from weave.trace.util import Thread as Thread
from weave.trace.util import ThreadPoolExecutor as ThreadPoolExecutor
from weave.type_handlers.Audio.audio import Audio
from weave.type_handlers.File.file import File
from weave.type_handlers.Markdown.markdown import Markdown
from weave.type_wrappers import Content

# Alias for succinct code
P = EasyPrompt

__all__ = [
    "Agent",
    "AgentState",
    "AnnotationSpec",
    "Audio",
    "Content",
    "Dataset",
    "EasyPrompt",
    "Evaluation",
    "EvaluationLogger",
    "File",
    "Markdown",
    "MessagesPrompt",
    "Model",
    "Monitor",
    "Object",
    "Prompt",
    "SavedView",
    "Scorer",
    "StringPrompt",
    "attributes",
    "finish",
    "get",
    "get_current_call",
    "init",
    "log_call",
    "op",
    "publish",
    "ref",
    "require_current_call",
    "set_view",
    "thread",
]
