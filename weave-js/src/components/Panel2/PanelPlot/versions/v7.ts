import * as TableState from '../../PanelTable/tableState';
import * as v1 from './v1';
import * as v6 from './v6';

export const MARK_OPTIONS = [...v1.MARK_OPTIONS, 'area' as const];

export type SeriesConfig = Omit<v6.SeriesConfig, 'constants' | 'dims'> & {
  constants: Omit<v6.SeriesConfig['constants'], 'mark'> & {
    mark: v6.SeriesConfig['constants']['mark'] | 'area';
  };
  dims: v6.SeriesConfig['dims'] & {
    y2: TableState.ColumnId;
  };
};

export type PlotConfig = Omit<v6.PlotConfig, 'series' | 'configVersion'> & {
  configVersion: 7;
  series: SeriesConfig[];
};

export const migrate = (config: v6.PlotConfig): PlotConfig => {
  return {
    ...config,
    configVersion: 7,
    series: config.series.map(series => {
      const newTable = TableState.appendEmptyColumn(series.table);
      const newColID = newTable.order[newTable.order.length - 1];
      return {
        ...series,
        table: newTable,
        dims: {
          ...series.dims,
          y2: newColID,
        },
      };
    }),
  };
};
