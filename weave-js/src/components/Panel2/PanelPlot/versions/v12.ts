import * as weave from '@wandb/weave/core';
import * as v10 from './v10';
import * as v11 from './v11';

type LazyStringOrNull = weave.Node<'string'> | weave.VoidNode;

export type LazySeriesConfig = Omit<
  v11.SeriesConfig,
  'constants' | 'axisSettings'
> & {
  constants: Omit<v11.SeriesConfig['constants'], 'mark'> & {
    mark: LazyStringOrNull | v11.SeriesConfig['constants']['mark'];
  };
};

const lazyPaths = [
  ['series' as const, 'constants' as const, 'mark' as const] as const,
  ['axisSettings' as const, 'x' as const, 'title' as const] as const,
  ['axisSettings' as const, 'y' as const, 'title' as const] as const,
  ['axisSettings' as const, 'color' as const, 'title' as const] as const,
];

export type LazyAxisSettings = {
  x: Omit<v10.AxisSetting, 'title'> & {
    title?: LazyStringOrNull | string;
  };
  y: Omit<v10.AxisSetting, 'title'> & {
    title?: LazyStringOrNull | string;
  };
  color: Omit<v10.AxisSetting, 'title'> & {
    title?: LazyStringOrNull | string;
  };
};

export type LazyPlotConfig = Omit<
  v11.PlotConfig,
  'configVersion' | 'series' | 'axisSettings'
> & {
  configVersion: 12;
  series: LazySeriesConfig[];
  axisSettings: LazyAxisSettings;
  lazyPaths: typeof lazyPaths;
};

export type ConcretePlotConfig = Omit<v11.PlotConfig, 'configVersion'> & {
  configVersion: 12;
};

export const migrateConcrete = (config: v11.PlotConfig): ConcretePlotConfig => {
  return {
    ...config,
    configVersion: 12,
  };
};

export const migrate = (config: v11.PlotConfig): LazyPlotConfig => {
  return {
    ...migrateConcrete(config),
    lazyPaths: [],
  };
};
