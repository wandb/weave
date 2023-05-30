import _ from 'lodash';

import * as v10 from './v10';

const VERSION = 11 as const;

export type ContinuousSelection = [number, number];
export type DiscreteSelection = string[];

export interface AxisSelections {
  x?: Selection;
  y?: Selection;
}

export type Selection = ContinuousSelection | DiscreteSelection;
export type Signals = {
  domain: AxisSelections;
  selection: AxisSelections;
};

export type SeriesConfig = Omit<v10.PlotConfig['series'][number], 'name'> & {
  seriesName?: string;
};

export type PlotConfig = Omit<v10.PlotConfig, 'configVersion' | 'series'> & {
  configVersion: typeof VERSION;
  signals: Signals;
  series: SeriesConfig[];
};

export const migrate = (config: v10.PlotConfig): PlotConfig => {
  return {
    ...config,
    configVersion: VERSION,
    signals: {
      domain: {},
      selection: {},
    },
    series: config.series.map(series => ({
      ...(_.omitBy(series, (value, key) => key === 'name') as Omit<
        v10.PlotConfig['series'][number],
        'name'
      >),
      seriesName: series.name,
    })),
  };
};
