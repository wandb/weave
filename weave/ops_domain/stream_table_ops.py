from ..panel import Panel
from ..decorator_type import type
from ..decorator_op import op
from .project_ops import project


@type()
class StreamTableType:
    entity_name: str
    project_name: str
    table_name: str


@type()
class StreamTablePanel(Panel):
    @op()
    def render(self):
        return (
            project(self.entity_name, self.project_name).run(self.table_name).history2()
        )
