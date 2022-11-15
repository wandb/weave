import contextvars
import typing
from wandb.apis import public
from .context_state import _wandb_api_key

WANDB_PUBLC_API: contextvars.ContextVar[
    typing.Optional[public.Api]
] = contextvars.ContextVar("WANDB_PUBLC_API", default=None)


def wandb_public_api() -> public.Api:
    current_key = _wandb_api_key.get()
    current_api = WANDB_PUBLC_API.get()
    default_api = public.Api(api_key=current_key)
    if current_api is None:
        WANDB_PUBLC_API.set(default_api)
        return default_api
    elif current_key is not None and current_api.api_key != current_key:
        raise ValueError("Dangerous: API_KEY != WANDB_PUBLC_API")
    return current_api
