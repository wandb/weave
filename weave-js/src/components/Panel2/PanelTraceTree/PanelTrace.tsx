import * as Panel2 from '../panel';
import React, {useMemo} from 'react';
import {TraceTreeSpanViewer} from './PanelTraceTreeTrace';
import {useNodeValue} from '@wandb/weave/react';
import {
  constFunction,
  constNumber,
  constString,
  listObjectType,
  opDict,
  opLimit,
  opMap,
  opNumberMult,
  opPick,
} from '@wandb/weave/core';
import {Loader} from 'semantic-ui-react';
import {flatToTrees, unifyRoots} from './util';

const inputType = {
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
      start_time_s: {
        type: 'union' as const,
        members: ['number' as const, 'none' as const],
      },
      end_time_s: {
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
};

type PanelTraceTreeTraceProps = Panel2.PanelProps<typeof inputType>;

const PanelTraceRender: React.FC<PanelTraceTreeTraceProps> = props => {
  const query = useMemo(() => {
    const limited = opLimit({arr: props.input, limit: constNumber(10000)});
    return opMap({
      arr: limited as any,
      mapFn: constFunction(
        {row: listObjectType(props.input.type), index: 'number'},
        ({row, index}) =>
          opDict({
            name: opPick({obj: row, key: constString('name')}),
            start_time_ms: opNumberMult({
              lhs: opPick({
                obj: row,
                key: constString('start_time_s'),
              }),
              rhs: constNumber(1000),
            }),
            end_time_ms: opNumberMult({
              lhs: opPick({
                obj: row,
                key: constString('end_time_s'),
              }),
              rhs: constNumber(1000),
            }),
            trace_id: opPick({obj: row, key: constString('trace_id')}),
            span_id: opPick({obj: row, key: constString('span_id')}),
            parent_id: opPick({obj: row, key: constString('parent_id')}),
          } as any)
      ),
    } as any);
  }, [props.input]);
  const nodeValue = useNodeValue(query);
  const tree = useMemo(
    () =>
      nodeValue.loading ? null : unifyRoots(flatToTrees(nodeValue.result)),
    [nodeValue.loading, nodeValue.result]
  );
  if (tree == null) {
    return <Loader />;
  }
  return <TraceTreeSpanViewer span={tree} />;
};

export const Spec: Panel2.PanelSpec = {
  id: 'Trace',
  canFullscreen: true,
  Component: PanelTraceRender,
  inputType,
};
