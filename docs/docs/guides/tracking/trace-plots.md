# Trace Plots

The _trace plots_ feature provides a way for you to visually analyze and understand key trace metrics across different time intervals, operations, models, or hosts. Metrics include cost, latency, and token usage. This guide walks you through how to use this feature and interpret the different chart types.

## Get started with trace plots

To open the trace plots view:

1. From your Weave project dashboard, navigate to the **Traces** tab.
2. (Optional) Apply a **Filter** to select relevant runs or evaluations.
3. Click **Show Metrics** to open the side pane with [default trace charts](#default-trace-charts).

## Default trace charts

When you first open the **Show Metrics** side pane, you’ll see three default visualizations:

- [Stacked Bar Chart (Cost over Time)](#stacked-bar-chart-cost-over-time)
- [Latency line chart](#latency-line-chart)

### Stacked bar chart (cost over time)

- Shows total cost grouped by operation (op).
- Automatically uses dynamic time binning (e.g., 4-second blocks).
- Supports zooming by selecting a region to drill into smaller time bins.

### Latency line chart

- Displays latency (e.g., P95) across the same time bins.
- By default, grouped by op.
- Includes:
  - Hover tooltips with per-bin values.
  - Shaded region highlighting based on cursor position.
  - Zoom in/out via horizontal or rectangular selection.

### Scatter plot

- Plots prompt tokens vs. completion tokens.
- Each point is color-coded by op.
- Clicking a point opens the associated trace in detail.

## Filtering and grouping

You can filter and group metrics by:

- Operation (op)
- Host
- Model
- Custom dimensions (if available)

Selecting a specific op disables default grouping, showing you an ungrouped line chart specific to that op.

## Chart settings

Click the settings gear icon to customize your trace plot:

### Y-axis metric options:

- Cost
- Latency (P95, P99, etc.)
- Exceptions
- Prompt Tokens
- Completion Tokens
- Inputs, Outputs
- Scores

### Additional controls:

- Chart type (Bar, Line, Scatter)
- Aggregation method (Sum, P95, P99, Count, etc.)
- Binning granularity
- Max number of calls (default: 250, configurable up to 1000)
