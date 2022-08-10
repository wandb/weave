import matplotlib
import networkx as nx_lib
import pyvis.network
from pylab import cm

import weave


class NetworkxType(weave.types.Type):
    instance_classes = nx_lib.Graph

    def save_instance(self, obj, artifact, name):

        with artifact.new_file(f"{name}.gml", binary=True) as f:
            nx_lib.write_gml(obj, f)

    def load_instance(self, artifact, name, extra=None):
        with artifact.open(f"{name}.gml", binary=True) as f:
            return nx_lib.read_gml(f)


@weave.op()
def render_graph_html(graph: nx_lib.Graph) -> weave.ops.Html:
    cmap_name = graph.graph.get("cmap", "Set2")
    cmap = cm.get_cmap(cmap_name)
    dim = ("300px", "300px")
    netw = pyvis.network.Network(*dim)
    netw.from_nx(graph)
    netw.inherit_edge_colors(False)
    netw.set_edge_smooth("discrete")

    labels = graph.graph.get("labels", [])

    for i, c in enumerate(labels):
        netw.nodes[i]["color"] = matplotlib.colors.rgb2hex(cmap(int(c)))

    return weave.ops.Html(netw.generate_html())


@weave.op()
def visualize(graph: weave.Node[nx_lib.Graph]) -> weave.panels.Card:

    return weave.panels.Card(
        title="",
        subtitle="Graph Visualization",
        content=[
            weave.panels.CardTab(
                name="Graph", content=weave.panels.Html(render_graph_html(graph))
            )
        ],
    )
