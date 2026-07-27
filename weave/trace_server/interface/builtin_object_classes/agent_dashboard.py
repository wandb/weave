"""Validated builtin object models for persisted agent dashboards."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from weave.trace_server.interface.builtin_object_classes import base_object_def

DASHBOARD_GRID_COLUMNS = 24
PanelValueFormat = Literal["number", "percent", "cost", "duration"]


class DashboardConfigModel(BaseModel):
    """Closed configuration model used by persisted dashboard components."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)


class PanelGridLayout(DashboardConfigModel):
    """Position and size of a panel in the dashboard's 24-column grid."""

    x: int = Field(ge=0, lt=DASHBOARD_GRID_COLUMNS)
    y: int = Field(ge=0)
    w: int = Field(ge=1, le=DASHBOARD_GRID_COLUMNS)
    h: int = Field(ge=1)

    @model_validator(mode="after")
    def validate_horizontal_bounds(self) -> PanelGridLayout:
        if self.x + self.w > DASHBOARD_GRID_COLUMNS:
            raise ValueError("panel layout extends beyond the dashboard grid")
        return self


class PanelQueryConfig(DashboardConfigModel):
    """Options shared by all supported dashboard panel queries."""

    version: int = Field(default=1, ge=1, le=1)
    metric: str = Field(min_length=1)
    filter: str = ""
    format: PanelValueFormat | None = None


class KpiPanelQueryConfig(PanelQueryConfig):
    """A scalar query; KPI panels do not support grouping or Top-N."""


class TimelinePanelQueryConfig(PanelQueryConfig):
    """A time-bucketed query with optional series grouping."""

    group_by: str | None = Field(default=None, alias="groupBy")
    limit: int | None = Field(default=None, ge=1, le=50)


class BreakdownPanelQueryConfig(PanelQueryConfig):
    """A grouped Top-N query used by breakdown panels."""

    group_by: str = Field(min_length=1, alias="groupBy")
    limit: int = Field(default=6, ge=1, le=50)


class KpiPanelSettings(DashboardConfigModel):
    """Supported configuration for a KPI panel."""

    query: KpiPanelQueryConfig
    title: str | None = None


class TimelinePanelSettings(DashboardConfigModel):
    """Supported configuration for a timeline panel."""

    query: TimelinePanelQueryConfig
    title: str | None = None


class BreakdownPanelSettings(DashboardConfigModel):
    """Supported configuration for a breakdown panel."""

    query: BreakdownPanelQueryConfig
    title: str | None = None


class DashboardPanelBase(DashboardConfigModel):
    """Fields shared by every supported dashboard panel."""

    id: str = Field(min_length=1)
    layout: PanelGridLayout


class KpiDashboardPanel(DashboardPanelBase):
    """A single-value KPI tile."""

    panel_type: Literal["kpi"]
    settings: KpiPanelSettings


class TimelineDashboardPanel(DashboardPanelBase):
    """A metric plotted over time."""

    panel_type: Literal["timeline"]
    settings: TimelinePanelSettings


class BreakdownDashboardPanel(DashboardPanelBase):
    """A metric grouped into ranked categorical rows."""

    panel_type: Literal["breakdown"]
    settings: BreakdownPanelSettings


DashboardPanel = KpiDashboardPanel | TimelineDashboardPanel | BreakdownDashboardPanel


class AgentDashboardDefinition(DashboardConfigModel):
    """The validated panels and grid layouts in an agent dashboard."""

    panels: list[DashboardPanel]


class AgentDashboard(base_object_def.BaseObject):
    """A saved agent dashboard configuration."""

    label: str
    definition: AgentDashboardDefinition


__all__ = [
    "AgentDashboard",
    "AgentDashboardDefinition",
    "BreakdownDashboardPanel",
    "BreakdownPanelQueryConfig",
    "BreakdownPanelSettings",
    "DashboardPanel",
    "KpiDashboardPanel",
    "KpiPanelQueryConfig",
    "KpiPanelSettings",
    "PanelGridLayout",
    "PanelQueryConfig",
    "PanelValueFormat",
    "TimelineDashboardPanel",
    "TimelinePanelQueryConfig",
    "TimelinePanelSettings",
]
