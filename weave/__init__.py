"""The top-level functions and classes for working with Weave."""

import sys
import warnings

if sys.version_info < (3, 10):  # noqa: UP036
    warnings.warn(
        "Weave only supports Python 3.10 or higher; please upgrade your Python version to avoid potential issues.",
        stacklevel=2,
    )

# Side-effect import: applies thread-safety patches to PIL and MoviePy.
import weave.initialization  # noqa: F401
from weave import version
from weave.trace.api import (
    ObjectRef,
    Table,
    ThreadContext,
    add_tags,
    as_op,
    attributes,
    finish,
    get,
    get_aliases,
    get_client,
    get_current_call,
    get_tags,
    get_tags_and_aliases,
    init,
    link_prompt_to_registry,
    list_aliases,
    list_tags,
    op,
    publish,
    ref,
    remove_aliases,
    remove_tags,
    require_current_call,
    set_aliases,
    set_view,
    thread,
    weave_client_context,
)

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
from weave.flow.monitor import ClassifierMonitor, Monitor
from weave.flow.saved_view import SavedView
from weave.flow.scorer import Scorer
from weave.object.obj import Object
from weave.prompt.prompt import EasyPrompt, MessagesPrompt, Prompt, StringPrompt
from weave.session.session import (
    LLM,
    LogResult,
    Message,
    Reasoning,
    Session,
    SubAgent,
    Tool,
    Turn,
    Usage,
    end_llm,
    end_session,
    end_turn,
    get_current_llm,
    get_current_session,
    get_current_turn,
    log_session,
    log_turn,
    start_llm,
    start_session,
    start_turn,
)
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
    "LLM",
    "Agent",
    "AgentState",
    "AnnotationSpec",
    "Audio",
    "ClassifierMonitor",
    "Content",
    "Dataset",
    "EasyPrompt",
    "Evaluation",
    "EvaluationLogger",
    "File",
    "LogResult",
    "Markdown",
    "Message",
    "MessagesPrompt",
    "Model",
    "Monitor",
    "Object",
    "ObjectRef",
    "Prompt",
    "Reasoning",
    "SavedView",
    "Scorer",
    "Session",
    "StringPrompt",
    "SubAgent",
    "Table",
    "ThreadContext",
    "Tool",
    "Turn",
    "Usage",
    "add_tags",
    "as_op",
    "attributes",
    "end_llm",
    "end_session",
    "end_turn",
    "finish",
    "get",
    "get_aliases",
    "get_client",
    "get_current_call",
    "get_current_llm",
    "get_current_session",
    "get_current_turn",
    "get_tags",
    "get_tags_and_aliases",
    "init",
    "link_prompt_to_registry",
    "list_aliases",
    "list_tags",
    "log_call",
    "log_session",
    "log_turn",
    "op",
    "publish",
    "ref",
    "remove_aliases",
    "remove_tags",
    "require_current_call",
    "set_aliases",
    "set_view",
    "start_llm",
    "start_session",
    "start_turn",
    "thread",
    "weave_client_context",
]
