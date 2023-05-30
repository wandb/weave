import * as TableState from '../../PanelTable/tableState';

export const MARK_OPTIONS = [
  'point' as const,
  'bar' as const,
  'boxplot' as const,
  'line' as const,
];
export type MarkOption = (typeof MARK_OPTIONS)[number];

export interface AxisSetting {
  scale?: any;
  noLabels?: boolean;
  noTitle?: boolean;
  noTicks?: boolean;
  title?: string;
}

export interface LegendSetting {
  noLegend?: boolean;
}

export interface PlotConfig {
  configVersion: 1;
  dims: {
    x: TableState.ColumnId;
    y: TableState.ColumnId;
    color: TableState.ColumnId;
    label: TableState.ColumnId;
    tooltip: TableState.ColumnId;
    pointSize: TableState.ColumnId;
    pointShape: TableState.ColumnId;
  };
  table: TableState.TableState;
  mark?: MarkOption;

  title?: string;
  axisSettings: {
    x: AxisSetting;
    y: AxisSetting;
    [key: string]: AxisSetting;
  };
  legendSettings: {
    color: LegendSetting;
    [key: string]: LegendSetting;
  };
  vegaOverlay?: any;
}
