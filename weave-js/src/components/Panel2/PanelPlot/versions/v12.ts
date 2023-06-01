import * as weave from '@wandb/weave/core';
import * as v10 from './v10';
import * as v11 from './v11';

export type LazySeriesConfig = Omit<
  v11.SeriesConfig,
  'constants' | 'axisSettings'
> & {
  constants: Omit<v11.SeriesConfig['constants'], 'mark'> & {
    mark: weave.Node<'string'> | weave.VoidNode;
  };
};

export type LazyAxisSettings = {
  x: Omit<v10.AxisSetting, 'title'> & {
    title: weave.Node<'string'> | weave.VoidNode;
  };
  y: Omit<v10.AxisSetting, 'title'> & {
    title: weave.Node<'string'> | weave.VoidNode;
  };
  color: Omit<v10.AxisSetting, 'title'> & {
    title: weave.Node<'string'> | weave.VoidNode;
  };
};

export type LazyPlotConfig = Omit<
  v11.PlotConfig,
  'configVersion' | 'series' | 'axisSettings'
> & {
  configType: 'lazy';
  configVersion: 12;
  series: LazySeriesConfig[];
  axisSettings: LazyAxisSettings;
};

export type ConcretePlotConfig = Omit<v11.PlotConfig, 'configVersion'> & {
  configType: 'concrete';
  configVersion: 12;
};

export const migrate = (config: v11.PlotConfig): LazyPlotConfig => {
  // noop migration, but if we are on version 12 we know that input configs can now be lazy
  return {
    ...config,
    configVersion: 12,
    configType: 'lazy',
    series: config.series.map(series => ({
      ...series,
      constants: {
        ...series.constants,
        mark:
          series.constants.mark == null
            ? weave.voidNode()
            : weave.constNodeUnsafe('string', series.constants.mark),
      },
    })),
    axisSettings: {
      x: {
        ...config.axisSettings.x,
        title:
          config.axisSettings.x.title == null
            ? weave.voidNode()
            : weave.constNodeUnsafe('string', config.axisSettings.x.title),
      },
      y: {
        ...config.axisSettings.y,
        title:
          config.axisSettings.y.title == null
            ? weave.voidNode()
            : weave.constNodeUnsafe('string', config.axisSettings.y.title),
      },
      color: {
        ...config.axisSettings.color,
        title:
          config.axisSettings.color.title == null
            ? weave.voidNode()
            : weave.constNodeUnsafe('string', config.axisSettings.color.title),
      },
    },
  };
};

export const migrateConcrete = (
  config: v11.PlotConfig
): ConcretePlotConfig => ({
  ...config,
  configType: 'concrete',
  configVersion: 12,
});
