from .. import panels
from .. import graph
from ..panel import Panel
from ..decorator_op import op
from ..ops_domain.project_ops import project
from ..types.stream_table_type import StreamTableType


@type()
class StreamTablePanel(Panel):
    input_node: graph.Node[StreamTableType]

    @op()
    def render(self) -> panels.Table:
        return (
            project(self.entity_name, self.project_name).run(self.table_name).history2()
        )
