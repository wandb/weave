import * as v1 from './v1';
import * as v2 from './v2';

export type MarkOption = v1.MarkOption | null;

export type SeriesConfig = Omit<v2.SeriesConfig, 'mark'> & {
  mark: MarkOption;
};

export type PlotConfig = Omit<v2.PlotConfig, 'configVersion' | 'series'> & {
  configVersion: 3;
  series: SeriesConfig[];
};

export function migrate(config: v2.PlotConfig): PlotConfig {
  return {
    ...config,
    configVersion: 3,
    series: config.series.map(series => ({
      ...series,
      mark: series.mark ?? null,
    })),
  };
}
