// Narrows the domain type of v12 to a more specific type than maybe(list(any))
// such as maybe(list(number)) or maybe(list(string))
// This fixes a bug where weave python didnt know how to deserialize these types

import * as weave from '@wandb/weave/core';

import {toWeaveType} from '../../toWeaveType';
import * as v12 from './v12';

export type Signals = Omit<v12.PlotConfig['signals'], 'domain'> & {
  domain: {
    x: weave.Node;
    y: weave.Node;
  };
};

export type PlotConfig = Omit<v12.PlotConfig, 'configVersion' | 'signals'> & {
  configVersion: 13;
  signals: Signals;
};

export type ConcretePlotConfig = Omit<
  v12.ConcretePlotConfig,
  'configVersion'
> & {
  configVersion: 13;
};

export const migrate = (config: v12.PlotConfig): PlotConfig => {
  // if we have const nodes for x or y, we need to narrow the type by looking at the values

  return {
    ...config,
    configVersion: 13,
    signals: {
      ...config.signals,
      domain: {
        x: weave.isConstNode(config.signals.domain.x)
          ? weave.constNode(
              toWeaveType(config.signals.domain.x.val),
              config.signals.domain.x.val
            )
          : config.signals.domain.x,
        y: weave.isConstNode(config.signals.domain.y)
          ? weave.constNode(
              toWeaveType(config.signals.domain.y.val),
              config.signals.domain.y.val
            )
          : config.signals.domain.y,
      },
    },
  };
};
