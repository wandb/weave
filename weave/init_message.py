import typing


def _print_version_check() -> None:
    import wandb
    import weave

    required_wandb_version = "0.16.4"
    parse_version = wandb.util.parse_version  # type: ignore
    if parse_version(required_wandb_version) > parse_version(wandb.__version__):
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
