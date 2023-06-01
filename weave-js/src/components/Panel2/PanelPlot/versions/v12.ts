import * as weave from '@wandb/weave/core';
import * as v10 from './v10';
import * as v11 from './v11';

export type SeriesConfig = Omit<
  v11.SeriesConfig,
  'constants' | 'axisSettings'
> & {
  constants: Omit<v11.SeriesConfig['constants'], 'mark'> & {
    mark: weave.Node<'string'> | weave.VoidNode;
  };
};

export type AxisSettings = {
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

export type PlotConfig = Omit<
  v11.PlotConfig,
  'configVersion' | 'series' | 'axisSettings'
> & {
  configVersion: 12;
  series: SeriesConfig[];
  axisSettings: AxisSettings;
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
