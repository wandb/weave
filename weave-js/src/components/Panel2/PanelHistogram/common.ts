import {opArray, opNumbersMax, opNumbersMin} from '@wandb/weave/core';
import {useMemo} from 'react';

import {useNodeValue} from '../../../react';
import {PanelProps} from '../panel';

export function useExtentFromData(node: PanelHistogramProps['input']): Extent {
  const extentNode = useMemo(() => {
    return opArray({
      0: opNumbersMin({numbers: node}),
      1: opNumbersMax({numbers: node}),
    } as any);
  }, [node]);

  const extentQuery = useNodeValue(extentNode);

  const dataExtent: Extent = useMemo(() => {
    if (extentQuery.loading) {
      return [undefined, undefined];
    }
    return extentQuery.result as Extent;
  }, [extentQuery]);

  return dataExtent;
}

export function defaultConfig(): HistogramConfig {
  return {
    mode: 'auto',
  };
}

export const inputType = {
  type: 'list' as const,
  objectType: {
    type: 'union' as const,
    members: ['none' as const, 'number' as const],
  },
};

// Properties besides mode in each variant of HistogramConfig should
// be disjoint, so that we can retain a "memory" of each config modes
export interface HistogramConfigAuto {
  mode: 'auto';
}

export interface HistogramConfigByNumBins {
  mode: 'num-bins';
  nBins?: number;
}

export interface HistogramConfigByBinSize {
  mode: 'bin-size';
  binSize?: number;
}

export type Extent = [min: number | undefined, max: number | undefined];

export type HistogramConfig = {
  // undefined in extent means min/max, respectively.
  extent?: Extent;
} & (HistogramConfigAuto | HistogramConfigByNumBins | HistogramConfigByBinSize);

export type PanelHistogramProps = PanelProps<typeof inputType, HistogramConfig>;
