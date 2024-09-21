import weave


def inheritors(klass):
    subclasses = set()
    work = [klass]
    while work:
        parent = work.pop()
        for child in parent.__subclasses__():
            if child not in subclasses:
                subclasses.add(child)
                work.append(child)
    return subclasses


def all_panels():
    return inheritors(weave.legacy.weave.panel.Panel)


def test_panel_coverage():
    panels = all_panels()
    panel_ids = set([p.id for p in panels])
    py_panels = set(panel_ids)
    missing_panels = list(js_registered_panels - py_panels)
    total_missing = len(missing_panels)
    error_msg = f"**{total_missing} Missing Panels**\n\n" + "\n".join(missing_panels)

    assert total_missing == 0, error_msg


js_registered_panels = set(
    [
        "Expression",
        "id-compare",
        "id-compare-count",
        "id-count",
        "type",
        "date",
        "boolean",
        "table",
        "plot",
        "Facet",
        "number",
        "barchart",
        "histogram",
        "precomputed-histogram",
        "multi-histogram",
        "string",
        "string-compare",
        "string-histogram",
        "multi-string-histogram",
        "none",
        "unknown",
        "link",
        "object",
        "project-overview",
        "run-overview",
        "run-color",
        "image-file",
        "image-file-compare",
        "jupyter",
        "rawimage",
        "markdown",
        "textdiff",
        "text",
        "netron",
        "tracer",
        "web-viz",
        "video-file",
        "audio-file",
        "html-file",
        "bokeh-file",
        "object3D-file",
        "molecule-file",
        "model-file",
        "dir",
        "ndarray",
        "artifactVersionAliases",
        "wb_trace_tree-traceDebugger",
        "wb_trace_tree-traceViewer",
        "wb_trace_tree-modelViewer",
        "debug-expression-graph",
    ]
)
