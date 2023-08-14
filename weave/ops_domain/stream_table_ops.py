from weave import weave_types
from ..ops_arrow.arrow import ArrowWeaveListType
from ..core_types import StreamTableType
from ..api import op
from .project_ops import project
from .. import compile
from .. import op_def


def _get_history_node(steam_table: StreamTableType):
    with op_def.no_refine():
        return (
            project(steam_table.entity_name, steam_table.project_name)
            .run(steam_table.table_name)
            .history3()
        )


@op()
def _rows_type(steam_table: StreamTableType) -> weave_types.Type:
    with compile.enable_compile():
        return compile.compile([_get_history_node(steam_table)])[0].type


@op(
    name="stream_table-rows",
    output_type=ArrowWeaveListType(weave_types.TypedDict({})),
    refine_output_type=_rows_type,
)
def rows(steam_table: StreamTableType):
    return _get_history_node(steam_table)
