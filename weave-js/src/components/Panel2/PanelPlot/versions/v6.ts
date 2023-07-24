import * as v2 from './v2';
import * as v4 from './v4';
import * as v5 from './v5';

export const POINT_SHAPES = [...v2.POINT_SHAPES, 'series' as const];
export const LINE_SHAPE_OPTIONS = [...v4.LINE_SHAPE_OPTIONS, 'series' as const];

export type SeriesConfig = Omit<v5.SeriesConfig, 'uiState' | 'constants'> & {
  uiState: v5.SeriesConfig['uiState'] & {
    label: 'expression' | 'dropdown';
  };
  constants: Omit<v5.SeriesConfig['constants'], 'pointShape' | 'lineStyle'> & {
    label: 'series';
    pointShape: v5.SeriesConfig['constants']['pointShape'] | 'series';
    lineStyle: v5.SeriesConfig['constants']['lineStyle'] | 'series';
  };
  name?: string;
};

export type PlotConfig = Omit<v5.PlotConfig, 'series' | 'configVersion'> & {
  configVersion: 6;
  series: SeriesConfig[];
};

export function migrate(config: v5.PlotConfig): PlotConfig {
  return {
    ...config,
    configVersion: 6,
    series: config.series.map(series => ({
      table: series.table,
      dims: series.dims,
      uiState: {...series.uiState, label: 'expression'},
      constants: {...series.constants, label: 'series'},
    })),
  };
}
