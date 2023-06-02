import * as weave from '@wandb/weave/core';
import * as v10 from './v10';
import * as v11 from './v11';

type LazyStringOrNull = weave.Node<'string'> | weave.VoidNode;

export type SeriesConfig = Omit<
  v11.SeriesConfig,
  'constants' | 'axisSettings'
> & {
  constants: Omit<v11.SeriesConfig['constants'], 'mark'> & {
    mark: LazyStringOrNull | v11.SeriesConfig['constants']['mark'];
  };
};

const lazyPaths = [
  'series.#.constants.mark' as const, // # means all array indices
  'axisSettings.x.title' as const,
  'axisSettings.y.title' as const,
  'axisSettings.color.title' as const,
];

export type AxisSettings = {
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

export type PlotConfig = Omit<
  v11.PlotConfig,
  'configVersion' | 'series' | 'axisSettings'
> & {
  configVersion: 12;
  series: SeriesConfig[];
  axisSettings: AxisSettings;
  lazyPaths: typeof lazyPaths;
};

// ConcretePlotConfig is a subtype of PlotConfig
export type ConcretePlotConfig = Omit<v11.PlotConfig, 'configVersion'> & {
  configVersion: 12;
};

export const migrate = (config: v11.PlotConfig): PlotConfig => {
  return {
    ...config,
    configVersion: 12,
    lazyPaths: [],
  };
};
