import {
  constFunction,
  constString,
  listObjectType,
  Node,
  opArray,
  opSort,
  opWBTraceTreeStartTime,
  opWBTraceTreeSummary,
  varNode,
  WeaveInterface,
} from '@wandb/weave/core';
import React, {useMemo} from 'react';

import {useWeaveContext} from '../../../context';
import * as Panel2 from '../panel';
import {emptyTable, getRowExampleNode} from '../PanelTable/tableState';
import {
  PanelTraceTreeTraceTableViewerCommon,
  updateTableState,
} from './panelTraceTreeTableViewerCommon';

const inputType = {
  type: 'list' as const,
  objectType: {
    type: 'union' as const,
    members: [{type: 'wb_trace_tree' as const}, 'none' as const],
  },
};

type PanelTraceTreeTraceTableViewerConfigType = {};

type PanelTraceTreeTraceTableViewerProps = Panel2.PanelProps<
  typeof inputType,
  PanelTraceTreeTraceTableViewerConfigType
>;

const makeTableState = (inputArrayNode: Node, weave: WeaveInterface) => {
  const ts = emptyTable();
  const exNode = getRowExampleNode(
    ts.preFilterFunction,
    ts.groupBy,
    ts.columnSelectFunctions,
    ts.columnNames,
    ts.order,
    ts.sort,
    inputArrayNode,
    weave
  );
  const modelTraceNode = varNode(exNode.type, 'row');
  return updateTableState(ts, modelTraceNode);
};

export const PanelTraceTreeTraceTableViewer: React.FC<
  PanelTraceTreeTraceTableViewerProps
> = props => {
  const rows = opSort({
    arr: props.input,
    compFn: constFunction({row: listObjectType(props.input.type)}, ({row}) =>
      opArray({a: opWBTraceTreeStartTime({trace_tree: row})} as any)
    ),
    columnDirs: opArray({a: constString('asc')} as any),
  });

  const tableNode = opWBTraceTreeSummary({
    trace_tree: rows,
  });

  const weave = useWeaveContext();
  const {ts, columnWidths} = useMemo(() => {
    return makeTableState(tableNode, weave);
  }, [tableNode, weave]);

  return (
    <PanelTraceTreeTraceTableViewerCommon
      tableNode={tableNode}
      traceArrayNode={props.input}
      initialTableState={ts}
      initialColumnWidths={columnWidths}
    />
  );
};

export const Spec: Panel2.PanelSpec = {
  id: 'wb_trace_tree-traceDebugger',
  displayName: 'LLM Trace Debugger',
  Component: PanelTraceTreeTraceTableViewer,
  inputType,
};
