import contextvars
from wandb.apis import public
from .context_state import _wandb_public_api


def wandb_public_api() -> public.Api:
    api = _wandb_public_api.get()
    if api:
        return api
    else:
        # The only way this branch works is if the system has an api key
        # available in a common location (ex: ~/.netrc). This should never
        # work in production, but is useful for local development.
        return public.Api()


def set_wandb_api_key(key: str):
    _wandb_public_api.set(public.Api(api_key=key))


def reset_wandb_api_key(token: contextvars.Token):
    _wandb_public_api.set(None)
