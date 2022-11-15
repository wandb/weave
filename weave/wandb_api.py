import contextlib
import contextvars
import typing
from wandb.apis import public
from .context_state import _wandb_api_key

WANDB_PUBLC_API: contextvars.ContextVar[
    typing.Optional[public.Api]
] = contextvars.ContextVar("WANDB_PUBLC_API", default=None)


def wandb_public_api() -> public.Api:
    api = WANDB_PUBLC_API.get()
    if api is None:
        raise ValueError("WANDB_PUBLC_API is not set")
    api_key = _wandb_api_key.get()
    if api_key is None:
        default_api = public.Api()
        if api.api_key != default_api.api_key:
            raise ValueError("Dangerous: DEFAUT_API_KEY != WANDB_PUBLC_API")
    elif api.api_key != api_key:
        raise ValueError("Dangerous: API_KEY != WANDB_PUBLC_API")
    return api


@contextlib.contextmanager
def wandb_api_session_context():
    WANDB_PUBLC_API.set(public.Api(api_key=_wandb_api_key.get()))
    try:
        yield
    finally:
        WANDB_PUBLC_API.set(None)
