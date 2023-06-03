import * as weave from '@wandb/weave/core';
import * as v10 from './v10';
import * as v11 from './v11';

type LazyStringOrNull = weave.Node<{
  type: 'union';
  members: ['string', 'none'];
}>;
type LazyAxisSelection = weave.Node<{
  type: 'union';
  members: [{type: 'list'; objectType: 'any'}, 'none'];
}>;

export type SeriesConfig = Omit<
  v11.SeriesConfig,
  'constants' | 'axisSettings'
> & {
  constants: Omit<v11.SeriesConfig['constants'], 'mark'> & {
    mark: LazyStringOrNull;
  };
};

export const LAZY_PATHS = [
  'series.#.constants.mark' as const, // # means all array indices
  'axisSettings.x.title' as const,
  'axisSettings.y.title' as const,
  'axisSettings.color.title' as const,
  'signals.domain.x' as const,
  'signals.domain.y' as const,
];

export type AxisSettings = {
  x: Omit<v10.AxisSetting, 'title'> & {
    title: LazyStringOrNull;
  };
  y: Omit<v10.AxisSetting, 'title'> & {
    title: LazyStringOrNull;
  };
  color: Omit<v10.AxisSetting, 'title'> & {
    title: LazyStringOrNull;
  };
};

export type Signals = Omit<v11.PlotConfig['signals'], 'domain'> & {
  domain: {
    x: LazyAxisSelection;
    y: LazyAxisSelection;
  };
};

export type PlotConfig = Omit<
  v11.PlotConfig,
  'configVersion' | 'series' | 'axisSettings' | 'signals'
> & {
  configVersion: 12;
  series: SeriesConfig[];
  axisSettings: AxisSettings;
  signals: Signals;
};

export type ConcretePlotConfig = Omit<v11.PlotConfig, 'configVersion'> & {
  configVersion: 12;
};

export const migrate = (config: v11.PlotConfig): PlotConfig => {
  return {
    ...config,
    configVersion: 12,
    series: config.series.map(series => ({
      ...series,
      constants: {
        ...series.constants,
        mark: weave.constNode(
          {type: 'union', members: ['string', 'none']},
          series.constants.mark
        ),
      },
    })),
    axisSettings: {
      x: {
        ...config.axisSettings.x,
        title: weave.constNode(
          {type: 'union', members: ['string', 'none']},
          config.axisSettings.x.title ?? null
        ),
      },
      y: {
        ...config.axisSettings.y,
        title: weave.constNode(
          {type: 'union', members: ['string', 'none']},
          config.axisSettings.y.title ?? null
        ),
      },
      color: {
        ...config.axisSettings.color,
        title: weave.constNode(
          {type: 'union', members: ['string', 'none']},
          config.axisSettings.color.title ?? null
        ),
      },
    },
    signals: {
      ...config.signals,
      domain: {
        x: weave.constNode(
          {type: 'union', members: [{type: 'list', objectType: 'any'}, 'none']},
          config.signals.domain.x ?? null
        ),
        y: weave.constNode(
          {type: 'union', members: [{type: 'list', objectType: 'any'}, 'none']},
          config.signals.domain.y ?? null
        ),
      },
    },
  };
};
