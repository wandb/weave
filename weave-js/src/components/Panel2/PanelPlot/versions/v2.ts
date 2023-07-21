import {constNumber, constString} from '@wandb/weave/core';

import * as TableState from '../../PanelTable/tableState';
import * as v1 from './v1';

export const POINT_SHAPES = [
  'circle' as const,
  'square' as const,
  'cross' as const,
  'diamond' as const,
  'triangle-up' as const,
  'triangle-down' as const,
  'triangle-right' as const,
  'triangle-left' as const,
];

export type PointShapeOption = (typeof POINT_SHAPES)[number];

export const PLOT_DIMS_UI = [
  'x' as const,
  'y' as const,
  'label' as const,
  'tooltip' as const,
  'mark' as const,
];

export interface SeriesConfig {
  dims: {
    x: TableState.ColumnId;

    // can have multiple y columns for 1 x
    y: TableState.ColumnId;

    color: TableState.ColumnId;
    label: TableState.ColumnId;
    tooltip: TableState.ColumnId;
    pointSize: TableState.ColumnId;
    pointShape: TableState.ColumnId;
  };
  table: TableState.TableState;

  // mark should only be read off of SeriesConfig, not off of PlotConfig
  mark?: v1.MarkOption;
}

export interface PlotConfig {
  configVersion: 2;
  title?: string;
  axisSettings: {
    x: v1.AxisSetting;
    y: v1.AxisSetting;
    [key: string]: v1.AxisSetting;
  };
  legendSettings: {
    color: v1.LegendSetting;
    [key: string]: v1.LegendSetting;
  };
  vegaOverlay?: any;
  series: SeriesConfig[];
  configOptionsExpanded: {
    [K in (typeof PLOT_DIMS_UI)[number] | 'mark']: boolean;
  };
}

export const DEFAULT_POINT_SIZE = 100;
export function migrate(oldConfig: v1.PlotConfig): PlotConfig {
  let config: PlotConfig;

  const addDefaultPointSizeAndShapeToDimsAndTable = (
    dims: v1.PlotConfig['dims'],
    table: TableState.TableState
  ): {
    dims: SeriesConfig['dims'];
    table: TableState.TableState;
  } => {
    const dimsToMerge: {
      pointShape: TableState.ColumnId;
      pointSize: TableState.ColumnId;
    } = {
      pointSize: dims.pointSize || '',
      pointShape: dims.pointShape || '',
    };

    if (!dims.pointSize) {
      const pointSizeRes = TableState.addColumnToTable(
        table,
        constNumber(DEFAULT_POINT_SIZE)
      );
      table = pointSizeRes.table;
      dimsToMerge.pointSize = pointSizeRes.columnId;
      table = TableState.updateColumnName(
        table,
        pointSizeRes.columnId,
        'pointSize'
      );
    }

    if (!dims.pointShape) {
      const pointShapeRes = TableState.addColumnToTable(
        table,
        constString('circle')
      );
      table = pointShapeRes.table;
      dimsToMerge.pointShape = pointShapeRes.columnId;
      table = TableState.updateColumnName(
        table,
        pointShapeRes.columnId,
        'pointShape'
      );
    }

    return {
      dims: {...dims, ...dimsToMerge},
      table,
    };
  };

  // config is in single-series format, migrate it to multi-series format
  const newSeries: SeriesConfig = addDefaultPointSizeAndShapeToDimsAndTable(
    oldConfig.dims,
    oldConfig.table
  );

  newSeries.mark = oldConfig.mark;

  config = {
    series: [newSeries],
    axisSettings: oldConfig.axisSettings,
    legendSettings: oldConfig.legendSettings,
    configVersion: 2,
    vegaOverlay: oldConfig.vegaOverlay,
    title: oldConfig.title,
    configOptionsExpanded: PLOT_DIMS_UI.reduce((acc, val) => {
      acc[val] = false;
      return acc;
    }, {} as PlotConfig['configOptionsExpanded']),
  };

  if (
    config.axisSettings == null ||
    config.axisSettings.x == null ||
    config.axisSettings.y == null
  ) {
    config = {
      ...config,
      axisSettings: {
        x: {},
        y: {},
      },
    };
  }
  if (config.legendSettings == null || config.legendSettings.color == null) {
    config = {
      ...config,
      legendSettings: {
        color: {},
      },
    };
  }
  return config;
}
