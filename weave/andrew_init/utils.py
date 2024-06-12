from typing import Optional

import sentry_sdk

from .. import errors, trace_sentry, wandb_api


def sentry_configure_scope(entity: str, project: str):
    username = get_username()
    user_context = {"username": username} if username else None
    trace_sentry.global_trace_sentry.configure_scope(
        {
            "entity_name": entity,
            "project_name": project,
            "user": user_context,
        }
    )


def sentry_reset_scope():
    with sentry_sdk.configure_scope() as scope:
        scope.clear()


def get_entity_project_from_project_name(project_name: str) -> tuple[str, str]:
    fields = project_name.split("/")
    if len(fields) == 1:
        api = wandb_api.get_wandb_api_sync()
        try:
            entity_name = api.default_entity_name()
        except AttributeError:
            raise errors.WeaveWandbAuthenticationException('weave init requires wandb. Run "wandb login"')
        project_name = fields[0]
    elif len(fields) == 2:
        entity_name, project_name = fields
    else:
        raise ValueError('project_name must be of the form "<project_name>" or "<entity_name>/<project_name>"')
    if not entity_name:
        raise ValueError("entity_name must be non-empty")

    return entity_name, project_name


# All of this stuff should be used in tsi from_env?
# TODO: this func is not ideally factored
def init_wandb_api_return_api_key(entity: str, project: str) -> str:
    # from .. import wandb_api

    wandb_api.init()
    wandb_api.check_base_url()

    if (wandb_context := wandb_api.get_wandb_api_context()) is None:
        import wandb

        print("Please login to Weights & Biases (https://wandb.ai/) to continue:")
        wandb.login(anonymous="never", force=True)
        wandb_api.init()
        wandb_context = wandb_api.get_wandb_api_context()

    # TODO: this should be refactored
    entity, project = get_entity_project_from_project_name(project)
    wandb_run_id = safe_current_wb_run_id()
    check_wandb_run_matches(wandb_run_id, entity, project)

    api_key = None
    if wandb_context is not None and wandb_context.api_key is not None:
        api_key = wandb_context.api_key
        wandb_api.check_api_key(api_key)

    # print init message
    from .. import urls

    username = get_username()
    print(f"Logged in as Weights & Biases user: {username}.")
    print(f"View Weave data at {urls.project_weave_root_url(entity, project)}")

    return api_key
    # remote_server = init_weave_get_server(api_key)


def safe_current_wb_run_id() -> Optional[str]:
    try:
        import wandb

        wandb_run = wandb.run
        if wandb_run is None:
            return None
        return f"{wandb_run.entity}/{wandb_run.project}/{wandb_run.id}"
    except ImportError:
        return None


def check_wandb_run_matches(wandb_run_id: Optional[str], weave_entity: str, weave_project: str) -> None:
    if wandb_run_id:
        # ex: "entity/project/run_id"
        wandb_entity, wandb_project, _ = wandb_run_id.split("/")
        if wandb_entity != weave_entity or wandb_project != weave_project:
            raise ValueError(
                f'Project Mismatch: weave and wandb must be initialized using the same project. Found wandb.init targeting project "{wandb_entity}/{wandb_project}" and weave.init targeting project "{weave_entity}/{weave_project}". To fix, please use the same project for both library initializations.'
            )


def get_username() -> Optional[str]:
    # from .. import wandb_api

    api = wandb_api.get_wandb_api_sync()
    try:
        return api.username()
    except AttributeError:
        return None
