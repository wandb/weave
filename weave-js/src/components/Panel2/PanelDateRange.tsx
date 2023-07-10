import React, {useCallback, useMemo} from 'react';

import * as Panel from './panel';
import * as ConfigPanel from './ConfigPanel';
import {
  NodeOrVoidNode,
  opNumbersMax,
  opNumbersMin,
  voidNode,
} from '@wandb/weave/core';
import {useUpdateConfig2} from './PanelComp';
import {useNodeValue} from '@wandb/weave/react';
import {monthRoundedTime} from '@wandb/weave/time';

const inputType = {
  type: 'union' as const,
  members: [
    'none' as const,
    {
      type: 'list' as const,
      objectType: {
        type: 'union' as const,
        members: ['none' as const, {type: 'timestamp' as const}],
      },
    },
  ],
};

interface PanelDateRangeConfig {
  domain: NodeOrVoidNode;
}
type PanelDateRangeProps = Panel.PanelProps<
  typeof inputType,
  PanelDateRangeConfig
>;

export function initializedPanelDateRange(): PanelDateRangeConfig {
  return {
    domain: voidNode(),
  };
}

export const PanelDateRangeConfigComponent: React.FC<
  PanelDateRangeProps
> = props => {
  const updateConfig2 = useUpdateConfig2(props);
  const config = props.config!;

  const updateDomain = useCallback(
    async (newExpr: NodeOrVoidNode) => {
      updateConfig2(oldConfig => {
        return {
          ...oldConfig,
          domain: newExpr,
        };
      });
    },
    [updateConfig2]
  );

  return (
    <>
      <ConfigPanel.ConfigOption label={`domain`}>
        <ConfigPanel.ExpressionConfigField
          expr={config.domain}
          setExpression={updateDomain}
        />
      </ConfigPanel.ConfigOption>
    </>
  );
};

export const PanelDateRange: React.FC<PanelDateRangeProps> = props => {
  const config = props.config!;
  const valueQuery = useNodeValue(props.input as any);
  const domainMin = useMemo(() => {
    return config.domain.nodeType === 'void'
      ? voidNode()
      : opNumbersMin({numbers: config.domain});
  }, [config.domain]);
  const domainMax = useMemo(() => {
    return config.domain.nodeType === 'void'
      ? voidNode()
      : opNumbersMax({numbers: config.domain});
  }, [config.domain]);

  const domainMinQuery = useNodeValue(domainMin);
  const domainMaxQuery = useNodeValue(domainMax);

  const {start, end} = useMemo(() => {
    if (valueQuery.result != null) {
      return {start: valueQuery.result[0], end: valueQuery.result[1]};
    }
    return {
      start: domainMinQuery.result,
      end: domainMaxQuery.result,
    };
  }, [domainMaxQuery.result, domainMinQuery.result, valueQuery.result]);

  const durationMillis = useMemo(() => {
    if (end == null || start == null) {
      return null;
    }
    return end - start;
  }, [end, start]);

  return (
    <div
      style={{
        height: '100%',
        paddingLeft: 16,
        display: 'flex',
        flexDirection: 'column',
      }}>
      <div>
        start {start == null ? 'none' : new Date(start).toLocaleString()}
      </div>
      <div>end {start == null ? 'none' : new Date(end).toLocaleString()}</div>
      {durationMillis != null && (
        <div>duration {monthRoundedTime(durationMillis / 1000)}</div>
      )}
    </div>
  );
};

export const Spec: Panel.PanelSpec = {
  hidden: true,
  id: 'DateRange',
  initialize: initializedPanelDateRange,
  ConfigComponent: PanelDateRangeConfigComponent,
  Component: PanelDateRange,
  inputType,
};
