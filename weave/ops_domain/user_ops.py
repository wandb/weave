from ..api import op
from . import wb_domain_types


@op(name="user-link")
def user_link(user: wb_domain_types.User) -> wb_domain_types.Link:
    return wb_domain_types.Link(user.user_name, f"/{user.user_name}")
