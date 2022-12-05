import weave

from .. import panel
from .. import panel_util
from .. import ops
from .. import graph


@weave.type()
class PanelMarkdown(panel.Panel):
    id = "markdown"

    def __init__(self, input_node=graph.VoidNode(), vars=None, config=None, **options):
        # Convert input_node here
        # TODO: Type adaptation should be done by render, not
        #     construction (ie the Panel should handle Markdown and File<Markdown>
        #     types)
        input_node = panel_util.make_node(input_node)
        if ops.MarkdownType().assign_type(input_node.type):
            input_node = ops.markdown_file(input_node)
        super().__init__(input_node=input_node, vars=vars)
