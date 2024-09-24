from weave_query.version import VERSION

from weave_query.weave_query.decorator_op import op


@op(
    name="executionEngine-serverVersion",
    hidden=True,
)
def server_version() -> str:
    return VERSION
