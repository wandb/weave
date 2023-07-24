import * as v3 from './v3';

export const LINE_SHAPE_OPTIONS = [
  'solid' as const,
  'dashed' as const,
  'dotted' as const,
  'dot-dashed' as const,
];

export type LineShapeOption = (typeof LINE_SHAPE_OPTIONS)[number];

export type SeriesConfig = v3.SeriesConfig & {
  lineShape: LineShapeOption;
};

export type PlotConfig = Omit<v3.PlotConfig, 'series' | 'configVersion'> & {
  configVersion: 4;
  series: SeriesConfig[];
};

export function migrate(config: v3.PlotConfig): PlotConfig {
  return {
    ...config,
    configVersion: 4,
    series: config.series.map(series => ({
      ...series,
      lineShape: 'solid',
    })),
  };
}
