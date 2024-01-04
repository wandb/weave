from .. import context_state as _context_state

_context_state._eager_mode.set(True)
from .. import logs

# If there is no WEAVE_LOG_LEVEL, this will set to ERROR
# from python's default which is WARNING
logs.configure_logger()

from .dataset import *
from .model import *
from .chat_model import *
from .structured_output import *

from .evaluate import *
from .evaluate2 import *
from .model_eval import *

from .openai import *
from .anyscale import *
from .huggingface import *

from .faiss import *
