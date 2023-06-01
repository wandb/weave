import * as weave from '@wandb/weave/core';
import * as v11 from './v11';

export type SeriesConfig = Omit<v11.SeriesConfig, 'constants'> & {
  constants: Omit<v11.SeriesConfig['constants'], 'mark'> & {
    mark: weave.Node<'string'> | weave.VoidNode;
  };
};

export type PlotConfig = Omit<v11.PlotConfig, 'configVersion' | 'series'> & {
  configVersion: 12;
  series: SeriesConfig[];
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
  };
};
