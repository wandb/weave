import {
  constFunction,
  constNumber,
  listObjectType,
  opLimit,
  opMap,
} from '@wandb/weave/core';
import {useNodeValue} from '@wandb/weave/react';
import React, {useCallback, useMemo} from 'react';
import {Loader} from 'semantic-ui-react';

import * as Panel2 from '../panel';
import {opSpanAsDictToLegacySpanShape} from './common';
import {TraceTreeSpanViewer} from './PanelTraceTreeTrace';
import {flatToTrees, SpanWeaveType, unifyRoots} from './util';

const inputType = {
  type: 'list' as const,
  objectType: SpanWeaveType,
};

type PanelTraceTreeTraceProps = Panel2.PanelProps<
  typeof inputType,
  {
    selectedSpanIndex?: number;
  }
>;

const PanelTraceRender: React.FC<PanelTraceTreeTraceProps> = props => {
  const query = useMemo(() => {
    const limited = opLimit({arr: props.input, limit: constNumber(10000)});
    return opMap({
      arr: limited as any,
      mapFn: constFunction(
        {row: listObjectType(props.input.type), index: 'number'},
        ({row, index}) => opSpanAsDictToLegacySpanShape({spanDict: row})
      ),
    } as any);
  }, [props.input]);
  const nodeValue = useNodeValue(query);
  const tree = useMemo(
    () =>
      nodeValue.loading ? null : unifyRoots(flatToTrees(nodeValue.result)),
    [nodeValue.loading, nodeValue.result]
  );
  const setSelectedSpanIndex = useCallback(
    (selectedSpanIndex: number) => {
      props.updateConfig({selectedSpanIndex});
    },
    [props]
  );
  if (tree == null) {
    return <Loader />;
  }

  return (
    <TraceTreeSpanViewer
      span={tree}
      selectedSpanIndex={props.config?.selectedSpanIndex}
      onSelectSpanIndex={setSelectedSpanIndex}
      hideDetails={true}
    />
  );
};

export const Spec: Panel2.PanelSpec = {
  id: 'tracePanel',
  canFullscreen: true,
  Component: PanelTraceRender,
  inputType,
};
