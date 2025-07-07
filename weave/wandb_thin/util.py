import os
from typing import Optional


def get_app_url() -> Optional[str]:
    return os.getenv("WANDB_APP_URL")


def app_url(api_url: str) -> str:
    """Return the frontend app url without a trailing slash."""
    app_url = get_app_url()
    if app_url is not None:
        return app_url.strip("/")
    if "://api.wandb.test" in api_url:
        # dev mode
        return api_url.replace("://api.", "://app.").strip("/")
    elif "://api.wandb." in api_url:
        # cloud
        return api_url.replace("://api.", "://").strip("/")
    elif "://api." in api_url:
        # onprem cloud
        return api_url.replace("://api.", "://app.").strip("/")
    # wandb/local
    return api_url
