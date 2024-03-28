import typing

if typing.TYPE_CHECKING:
    import packaging.version  # type: ignore[import-not-found]

REQUIRED_WANDB_VERSION = "0.16.4"


def _parse_version(version: str) -> "packaging.version.Version":
    """Parse a version string into a version object.

    This function is a wrapper around the `packaging.version.parse` function, which
    is used to parse version strings into version objects. If the `packaging` library
    is not installed, it falls back to the `pkg_resources` library.
    """
    try:
        from packaging.version import parse as parse_version  # type: ignore
    except ImportError:
        from pkg_resources import parse_version

    return parse_version(version)


def _print_version_check() -> None:
    import wandb
    import weave

    if _parse_version(REQUIRED_WANDB_VERSION) > _parse_version(wandb.__version__):
        message = (
            "wandb version >= 0.16.4 is required.  To upgrade, please run:\n"
            " $ pip install wandb --upgrade"
        )
        print(message)
    else:
        wandb_messages = wandb.sdk.internal.update.check_available(wandb.__version__)
        if wandb_messages:
            # Don't print the upgrade message, only the delete or yank message
            use_message = wandb_messages.get("delete_message") or wandb_messages.get(
                "yank_message"
            )  #  or wandb_messages.get("upgrade_message")
            if use_message:
                print(use_message)

    orig_module = wandb._wandb_module
    wandb._wandb_module = "weave"
    weave_messages = wandb.sdk.internal.update.check_available(weave.__version__)
    wandb._wandb_module = orig_module

    if weave_messages:
        use_message = (
            weave_messages.get("delete_message")
            or weave_messages.get("yank_message")
            or weave_messages.get("upgrade_message")
        )
        if use_message:
            print(use_message)


def print_init_message(
    username: typing.Optional[str],
    entity_name: str,
    project_name: str,
    host: str = "https://wandb.ai",
) -> None:
    try:
        _print_version_check()
    except Exception as e:
        pass

    message = ""
    if username is not None:
        message += f"Logged in as W&B user {username}.\n"
    message += f"View Weave data at {host}/{entity_name}/{project_name}/weave"

    print(message)
