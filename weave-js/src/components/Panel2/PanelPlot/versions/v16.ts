import {DropdownWithExpressionMode} from './v5';
import * as v11 from './v11';
import * as v15 from './v15';

export type SeriesConfig = Omit<v11.SeriesConfig, 'uiState'> & {
  uiState: v11.SeriesConfig['uiState'] & {
    x: DropdownWithExpressionMode;
    y: DropdownWithExpressionMode;
    tooltip: DropdownWithExpressionMode;
  };
};

type Diff = {
  configVersion: 16;
  series: SeriesConfig[];
};

export type PlotConfig = Omit<v15.PlotConfig, 'configVersion' | 'series'> &
  Diff;
export type ConcretePlotConfig = Omit<
  v15.ConcretePlotConfig,
  'configVersion' | 'series'
> &
  Diff;

export const migrate = (config: v15.PlotConfig): PlotConfig => {
  const schema = {
    ...config,
    configVersion: 16 as 16,
    series: config.series.map(series => ({
      ...series,
      uiState: {
        ...series.uiState,
        x: 'dropdown' as 'dropdown',
        y: 'dropdown' as 'dropdown',
        tooltip: 'dropdown' as 'dropdown',
      },
    })),
  };
  return schema;
};
