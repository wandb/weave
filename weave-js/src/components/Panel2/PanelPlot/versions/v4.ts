import * as v2 from './v2';
import * as v3 from './v3';

export const LINE_SHAPE_OPTIONS = [
  'solid' as const,
  'dashed' as const,
  'dotted' as const,
  'dot-dashed' as const,
];

export const DIM_NAME_MAP = {
  ...v2.DIM_NAME_MAP,
  lineShape: 'Style',
};

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
