from ..decorator_op import op
from ..version import VERSION


@op(
    name="executionEngine-serverVersion",
    hidden=True,
)
def server_version() -> str:
    return VERSION
