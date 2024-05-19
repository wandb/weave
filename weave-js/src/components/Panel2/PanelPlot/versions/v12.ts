import * as weave from '@wandb/weave/core';

import * as v11 from './v11';

type LazyAxisSelection = weave.Node<{
  type: 'union';
  members: [{type: 'list'; objectType: 'any'}, 'none'];
}>;

export const LAZY_PATHS = [
  'signals.domain.x' as const,
  'signals.domain.y' as const,
];

export const DEFAULT_LAZY_PATH_VALUES: {
  [K in (typeof LAZY_PATHS)[number]]: Exclude<any, weave.Node>;
} = {
  'signals.domain.x': null,
  'signals.domain.y': null,
};

export type Signals = Omit<v11.PlotConfig['signals'], 'domain'> & {
  domain: {
    x: LazyAxisSelection;
    y: LazyAxisSelection;
  };
};

export type PlotConfig = Omit<v11.PlotConfig, 'configVersion' | 'signals'> & {
  configVersion: 12;
  signals: Signals;
};

export type ConcretePlotConfig = Omit<v11.PlotConfig, 'configVersion'> & {
  configVersion: 12;
};

export const migrate = (config: v11.PlotConfig): PlotConfig => {
  return {
    ...config,
    configVersion: 12,
    signals: {
      ...config.signals,
      domain: {
        x: weave.constNode(
          // this is problematic because weave python doesnt know
          // how to deserialize 'any' if its a number. this is why
          // we will update this in version 13
          {type: 'union', members: [{type: 'list', objectType: 'any'}, 'none']},
          config.signals.domain.x ?? null
        ),
        y: weave.constNode(
          // this is problematic because weave python doesnt know
          // how to deserialize 'any' if its a number. this is why
          // we will update this in version 13
          {type: 'union', members: [{type: 'list', objectType: 'any'}, 'none']},
          config.signals.domain.y ?? null
        ),
      },
    },
  };
};
