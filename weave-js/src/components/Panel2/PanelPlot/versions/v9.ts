import * as v7 from './v7';
import * as v8 from './v8';

export const LINE_SHAPE_OPTIONS = [
  'solid' as const,
  'dashed' as const,
  'dotted' as const,
  'dot-dashed' as const,
  'short-dashed' as const,
  'series' as const,
];

export type SeriesConfig = Omit<v7.SeriesConfig, 'constants'> & {
  constants: Omit<v7.SeriesConfig['constants'], 'lineStyle'> & {
    lineStyle: v7.SeriesConfig['constants']['lineStyle'] | 'short-dashed';
  };
};

export type PlotConfig = Omit<v8.PlotConfig, 'series' | 'configVersion'> & {
  configVersion: 9;
  series: SeriesConfig[];
};

export const migrate = (config: v8.PlotConfig): PlotConfig => {
  return {
    ...config,
    configVersion: 9,
  };
};
