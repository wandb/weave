import * as weave from '@wandb/weave/core';
import * as v10 from './v10';
import * as v11 from './v11';

type LazyStringOrNull = weave.Node<{
  type: 'union';
  members: ['string', 'none'];
}>;
type LazyDomain = weave.Node<{
  type: 'typedDict';
  propertyTypes: {
    x: 'none' | {type: 'list'; objectType: 'any'};
    y: 'none' | {type: 'list'; objectType: 'any'};
  };
}>;

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
  'signals.domain' as const,
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

export type Signals = Omit<v11.PlotConfig['signals'], 'domain'> & {
  domain: v11.PlotConfig['signals']['domain'] | LazyDomain;
};

export type PlotConfig = Omit<
  v11.PlotConfig,
  'configVersion' | 'series' | 'axisSettings' | 'signals'
> & {
  configVersion: 12;
  series: SeriesConfig[];
  axisSettings: AxisSettings;
  lazyPaths: typeof lazyPaths;
  signals: Signals;
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
