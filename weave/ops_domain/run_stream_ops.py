from weave import weave_types
from ..ops_arrow.arrow import ArrowWeaveListType
from ..core_types import RunStreamType
from ..api import op
from .project_ops import project
from .. import compile


def _get_history_node(steam_table: RunStreamType):
    return (
        project(steam_table.entity_name, steam_table.project_name)
        .run(steam_table.run_name)
        .history2()
    )


@op()
def _rows_type(steam_table: RunStreamType) -> weave_types.Type:
    with compile.enable_compile():
        return compile.compile([_get_history_node(steam_table)])[0].type


@op(
    name="run_stream-rows",
    output_type=ArrowWeaveListType(weave_types.TypedDict({})),
    refine_output_type=_rows_type,
    returns_expansion_node=True,
)
def rows(steam_table: RunStreamType):
    return _get_history_node(steam_table)
