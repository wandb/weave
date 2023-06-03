import * as helpers from '@wandb/weave/core/model/helpers';
import * as weave from '@wandb/weave/core';
import * as v10 from './v10';
import * as v11 from './v11';

const maybeString = helpers.maybe('string');
const maybeListOfAny = helpers.maybe(helpers.list('any'));

type LazyStringOrNull = weave.Node<typeof maybeString>;
type LazyAxisSelection = weave.Node<typeof maybeListOfAny>;

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
        mark:
          series.constants.mark == null
            ? weave.constNone()
            : weave.constString(series.constants.mark),
      },
    })),
    axisSettings: {
      x: {
        ...config.axisSettings.x,
        title:
          config.axisSettings.x.title == null
            ? weave.constNone()
            : weave.constString(config.axisSettings.x.title),
      },
      y: {
        ...config.axisSettings.y,
        title:
          config.axisSettings.y.title == null
            ? weave.constNone()
            : weave.constString(config.axisSettings.y.title),
      },
      color: {
        ...config.axisSettings.color,
        title:
          config.axisSettings.color.title == null
            ? weave.constNone()
            : weave.constString(config.axisSettings.color.title),
      },
    },
    signals: {
      ...config.signals,
      domain: {
        x:
          config.signals.domain.x == null
            ? weave.constNone()
            : weave.constNodeUnsafe(maybeListOfAny, config.signals.domain.x),
        y:
          config.signals.domain.y == null
            ? weave.constNone()
            : weave.constNodeUnsafe(maybeListOfAny, config.signals.domain.y),
      },
    },
  };
};
