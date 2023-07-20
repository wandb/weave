import * as Panel2 from '../panel';
import React, {useCallback, useMemo} from 'react';
import {TraceTreeSpanViewer} from './PanelTraceTreeTrace';
import {useNodeValue} from '@wandb/weave/react';
import {constNumber, opLimit} from '@wandb/weave/core';
import {Loader} from 'semantic-ui-react';
import {flatToTrees, unifyRoots} from './util';

const inputType = {
  type: 'union' as const,
  members: [
    'none' as const,
    {
      type: 'list' as const,
      objectType: {
        type: 'typedDict' as const,
        propertyTypes: {
          trace_id: {
            type: 'union' as const,
            members: ['string' as const, 'none' as const],
          },
          span_id: {
            type: 'union' as const,
            members: ['string' as const, 'none' as const],
          },
          parent_id: {
            type: 'union' as const,
            members: ['string' as const, 'none' as const],
          },
          name: {
            type: 'union' as const,
            members: ['string' as const, 'none' as const],
          },
          start_time_ms: {
            type: 'union' as const,
            members: ['number' as const, 'none' as const],
          },
          end_time_ms: {
            type: 'union' as const,
            members: ['number' as const, 'none' as const],
          },
          attributes: {
            type: 'union' as const,
            members: [
              {type: 'typedDict' as const, propertyTypes: {}},
              'none' as const,
            ],
          },
        },
      },
    },
  ],
};

type PanelTraceTreeTraceProps = Panel2.PanelProps<
  typeof inputType,
  {selectedSpan?: any}
>;

const PanelTraceRender: React.FC<PanelTraceTreeTraceProps> = props => {
  const query = useMemo(() => {
    const limited = opLimit({arr: props.input, limit: constNumber(10000)});
    return limited;
  }, [props.input]);
  const nodeValue = useNodeValue(query);
  console.log({nodeValue});
  const tree = useMemo(
    () =>
      nodeValue.loading ? null : unifyRoots(flatToTrees(nodeValue.result)),
    [nodeValue.loading, nodeValue.result]
  );

  const updateSelectedSpan = useCallback(
    span => {
      console.log({span});
      props.updateConfig({selectedSpan: span});
    },
    [props]
  );
  if (tree == null) {
    return <Loader />;
  }
  return (
    <TraceTreeSpanViewer span={tree} updateSelectedSpan={updateSelectedSpan} />
  );
};

export const Spec: Panel2.PanelSpec = {
  id: 'tracePanel',
  displayName: 'Trace',
  canFullscreen: true,
  Component: PanelTraceRender,
  inputType,
};
