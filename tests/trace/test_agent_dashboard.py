import pytest
from pydantic import ValidationError

from weave.trace_server.interface.builtin_object_classes.agent_dashboard import (
    AgentDashboard,
)


def dashboard_value(panels: list[dict[str, object]]) -> dict[str, object]:
    return {
        "label": "Agent reliability",
        "definition": {"panels": panels},
    }


def panel_value(
    panel_type: str,
    query: dict[str, object],
    *,
    settings_extra: dict[str, object] | None = None,
    layout: dict[str, int] | None = None,
) -> dict[str, object]:
    return {
        "id": f"{panel_type}-panel",
        "panel_type": panel_type,
        "layout": layout or {"x": 0, "y": 0, "w": 6, "h": 4},
        "settings": {
            "title": "Panel title",
            "query": query,
            **(settings_extra or {}),
        },
    }


def test_agent_dashboard_validates_supported_panel_variants() -> None:
    dashboard = AgentDashboard.model_validate(
        dashboard_value(
            [
                panel_value(
                    "kpi",
                    {
                        "version": 1,
                        "metric": "count_distinct(conversation.id)",
                        "filter": "",
                        "format": "number",
                    },
                ),
                panel_value(
                    "timeline",
                    {
                        "version": 1,
                        "metric": "avg(span.duration_ms)",
                        "filter": 'span.provider_name = "openai"',
                        "groupBy": "custom_attrs_string.customer.tier",
                        "limit": 8,
                        "format": "duration",
                    },
                ),
                panel_value(
                    "breakdown",
                    {
                        "version": 1,
                        "metric": "error_rate(turn.id)",
                        "filter": "",
                        "groupBy": "agent_version",
                        "limit": 6,
                        "format": "percent",
                    },
                ),
            ]
        )
    )

    assert dashboard.model_dump(mode="json", by_alias=True, exclude_none=True) == {
        "label": "Agent reliability",
        "definition": {
            "panels": [
                panel_value(
                    "kpi",
                    {
                        "version": 1,
                        "metric": "count_distinct(conversation.id)",
                        "filter": "",
                        "format": "number",
                    },
                ),
                panel_value(
                    "timeline",
                    {
                        "version": 1,
                        "metric": "avg(span.duration_ms)",
                        "filter": 'span.provider_name = "openai"',
                        "groupBy": "custom_attrs_string.customer.tier",
                        "limit": 8,
                        "format": "duration",
                    },
                ),
                panel_value(
                    "breakdown",
                    {
                        "version": 1,
                        "metric": "error_rate(turn.id)",
                        "filter": "",
                        "groupBy": "agent_version",
                        "limit": 6,
                        "format": "percent",
                    },
                ),
            ]
        },
    }


@pytest.mark.parametrize(
    "panel",
    [
        panel_value("heatmap", {"version": 1, "metric": "count()", "filter": ""}),
        panel_value(
            "kpi",
            {"version": 1, "metric": "count()", "filter": "", "groupBy": "tool_name"},
        ),
        panel_value(
            "timeline",
            {"version": 1, "metric": "count()", "filter": "", "limit": 51},
        ),
        panel_value(
            "timeline",
            {"version": 1, "metric": "count()", "filter": "", "format": "bytes"},
        ),
        panel_value(
            "breakdown",
            {"version": 1, "metric": "count()", "filter": ""},
        ),
        panel_value(
            "timeline",
            {"version": 1, "metric": "count()", "filter": ""},
            settings_extra={"color": "purple"},
        ),
        panel_value(
            "timeline",
            {"version": 1, "metric": "count()", "filter": "", "color": "purple"},
        ),
        panel_value(
            "timeline",
            {"version": 1, "metric": "count()", "filter": ""},
            layout={"x": 20, "y": 0, "w": 6, "h": 4},
        ),
    ],
    ids=[
        "unsupported-panel-type",
        "kpi-grouping",
        "limit-out-of-range",
        "unsupported-format",
        "breakdown-without-grouping",
        "unknown-settings-option",
        "unknown-query-option",
        "layout-out-of-bounds",
    ],
)
def test_agent_dashboard_rejects_unsupported_configuration(
    panel: dict[str, object],
) -> None:
    with pytest.raises(ValidationError):
        AgentDashboard.model_validate(dashboard_value([panel]))
