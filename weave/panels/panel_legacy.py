"""
There are a number of panels defined in the JS implementation that are not
defined in the Python implementation. A dev can determine the total list of
panels by inspecting the panels in PanelRegistry.tsx. This is tested in
test_panel_coverage.py.

It is expected that panels with specific configuration options may be extracted
from this list and defined manually.
"""

import dataclasses
import typing
import weave


@dataclasses.dataclass
class LPanel:
    panel_id: str
    typename_override: typing.Optional[str] = None


panels = [
    LPanel("barchart", "PanelBarchart"),
    LPanel("web-viz", "PanelWebViz"),
    LPanel("video-file", "PanelVideoFile"),
    LPanel("model-file", "PanelModelFile"),
    LPanel("id-count", "PanelIdCount"),
    LPanel("wb_trace_tree-traceDebugger"),
    LPanel("link", "PanelLink"),
    LPanel("run-overview", "PanelRunOverview"),
    LPanel("none", "PanelNone"),
    LPanel("artifactVersionAliases", "PanelArtifactVersionAliases"),
    LPanel("netron", "PanelNetron"),
    LPanel("object", "PanelObject"),
    LPanel("audio-file", "PanelAudioFile"),
    LPanel("string-histogram", "PanelStringHistogram"),
    LPanel("rawimage", "PanelRawimage"),
    LPanel("precomputed-histogram", "PanelPrecomputedHistogram"),
    LPanel("image-file-compare", "PanelImageFileCompare"),
    LPanel("molecule-file", "PanelMoleculeFile"),
    LPanel("multi-histogram", "PanelMultiHistogram"),
    LPanel("object3D-file", "PanelObject3DFile"),
    LPanel("run-color", "PanelRunColor"),
    LPanel("multi-string-histogram", "PanelMultiStringHistogram"),
    LPanel("dir", "PanelDir"),
    LPanel("id-compare-count", "PanelIdCompareCount"),
    LPanel("jupyter", "PanelJupyter"),
    LPanel("bokeh-file", "PanelBokehFile"),
    LPanel("ndarray", "PanelNdarray"),
    LPanel("id-compare", "PanelIdCompare"),
    LPanel("unknown", "PanelUnknown"),
    LPanel("image-file", "PanelImageFile"),
    LPanel("project-overview", "PanelProjectOverview"),
    LPanel("textdiff", "PanelTextdiff"),
    LPanel("type", "PanelType"),
    LPanel("text", "PanelText"),
    LPanel("string-compare", "PanelStringCompare"),
    LPanel("debug-expression-graph", "PanelDebugExpressionGraph"),
    LPanel("tracer", "PanelTracer"),
    LPanel("projection.plot", "projection.plot"),
    LPanel("RootBrowser", "RootBrowser"),
    LPanel("row.runs-table.row.projection.plot", "row.runs-table.row.projection.plot"),
    LPanel("maybe.plot", "maybe.plot"),
    LPanel("maybe.wb_trace_tree-traceViewer", "maybe.wb_trace_tree-traceViewer"),
]

did_define = False


def define_panel(p: LPanel):
    class DummyClass(weave.panel.Panel):
        id = p.panel_id

    name = p.typename_override or p.panel_id
    if weave.types.type_name_to_type(name) is not None:
        raise RuntimeError(f"Panel {name} already defined")
    return weave.type(__override_name=name)(DummyClass)  # type: ignore


if not did_define:
    for p in panels:
        define_panel(p)
        if p.typename_override is not None:
            define_panel(LPanel("maybe." + p.panel_id, "maybe." + p.panel_id))

did_define = True
