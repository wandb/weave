import * as v2 from './v2';
import * as v4 from './v4';

export type DropdownWithExpressionMode = 'expression' | 'dropdown';

export type SeriesConfig = Omit<v4.SeriesConfig, 'mark' | 'lineShape'> & {
  uiState: {
    pointShape: DropdownWithExpressionMode;
  };

  constants: {
    mark: v4.SeriesConfig['mark'];
    lineStyle: v4.SeriesConfig['lineShape'];
    pointShape: v2.PointShapeOption;
  };
};

export type PlotConfig = Omit<v4.PlotConfig, 'series' | 'configVersion'> & {
  configVersion: 5;
  series: SeriesConfig[];
};

export function migrate(config: v4.PlotConfig): PlotConfig {
  return {
    ...config,
    configVersion: 5,
    series: config.series.map(series => ({
      table: series.table,
      dims: series.dims,
      constants: {
        mark: series.mark,
        lineStyle: series.lineShape,
        pointShape: 'circle',
      },
      uiState: {
        pointShape: 'expression',
      },
    })),
  };
}
