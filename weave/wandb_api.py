from wandb.apis import public


def wandb_public_api():
    from .context import _wandb_api_key

    return public.Api(api_key=_wandb_api_key.get())
