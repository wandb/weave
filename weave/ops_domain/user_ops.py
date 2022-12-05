from ..api import op
from . import wb_domain_types
from . import wandb_domain_gql


@op(name="root-viewer")
def root_viewer() -> wb_domain_types.User:
    return wandb_domain_gql.root_viewer()


@op(name="root-user")
def root_user(userName: str) -> wb_domain_types.User:
    return wb_domain_types.User(userName)


@op(name="user-link")
def user_link(user: wb_domain_types.User) -> wb_domain_types.Link:
    return wb_domain_types.Link(user.user_name, f"/{user.user_name}")


@op(name="user-entities")
def user_entities(user: wb_domain_types.User) -> list[wb_domain_types.Entity]:
    return wandb_domain_gql.user_entities(user)
