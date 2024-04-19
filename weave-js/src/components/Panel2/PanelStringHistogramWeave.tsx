/* This does all the histogram logic with Weave ops, so it scales
   much better than PanelStringHistogram. But it does not include all the
   color features of PanelStringHistogram.

   TODO: Implement PanelStringHistogram body using PanelPlot!
*/

/* eslint-disable no-template-curly-in-string */
import CustomPanelRenderer from '@wandb/weave/common/components/Vega3/CustomPanelRenderer';
import {
  Node,
  opCount,
  OutputNode,
  varNode,
  WeaveInterface,
} from '@wandb/weave/core';
import {produce} from 'immer';
import React from 'react';
import {useInView} from 'react-intersection-observer';
import {VisualizationSpec} from 'react-vega';
import {AutoSizer} from 'react-virtualized';

import {useWeaveContext} from '../../context';
import {useGatedValue} from '../../hookUtils';
import * as CGReact from '../../react';
import * as Panel2 from './panel';
import {Panel2Loader} from './PanelComp';
import * as TableState from './PanelTable/tableState';

const inputType = {
  type: 'list' as const,
  objectType: {
    type: 'union' as const,
    members: ['none' as const, 'string' as const],
  },
};

interface Table2DProps {
  label: OutputNode;
  value: OutputNode;
  source: Node;
}

const define2DTable = (props: Table2DProps, weave: WeaveInterface) => {
  const {label, value, source} = props;

  let table = TableState.emptyTable(); // Array of runs
  let labelCol: string;

  // Add label column
  ({table, columnId: labelCol} = TableState.addColumnToTable(table, label));

  // Add value column
  ({table} = TableState.addColumnToTable(table, value));

  // Enable grouping by new columns created above
  table = produce(table, draft => {
    draft.groupBy = [labelCol];
    // draft.sort = [{columnId: valueCol, dir: 'desc'}];
  });

  const {resultNode} = TableState.tableGetResultTableNode(table, source, weave);

  return {resultNode, table, sourceNode: source};
};

type PanelStringHistogramWeaveProps = Panel2.PanelProps<typeof inputType>;

const PanelStringHistogramWeave: React.FC<
  PanelStringHistogramWeaveProps
> = props => {
  const {ref, inView} = useInView();
  const hasBeenOnScreen = useGatedValue(inView, o => o);
  return (
    <div ref={ref} style={{width: '100%', height: '100%'}}>
      {hasBeenOnScreen ? (
        <AutoSizer style={{width: '100%', height: '100%'}}>
          {({width, height}) => (
            <PanelStringHistogramInner
              {...props}
              width={width}
              height={height}
            />
          )}
        </AutoSizer>
      ) : (
        <div
          style={{
            backgroundColor: '#eee',
            width: '100%',
            height: '100%',
          }}
        />
      )}
    </div>
  );
};

const BAR_CHART: VisualizationSpec = {
  $schema: 'https://vega.github.io/schema/vega-lite/v4.json',
  description: 'A simple bar chart',
  data: {
    name: 'wandb',
  },
  title: '${string:title}',
  mark: {
    type: 'bar',
    tooltip: {
      content: 'data',
    },
  },
  encoding: {
    x: {
      field: '${field:value}',
      type: 'quantitative',
      stack: null,
      axis: {
        title: null,
      },
    },
    y: {
      field: '${field:label}',
      type: 'nominal',
      axis: {
        title: null,
      },
    },
    opacity: {
      value: 0.6,
    },
  },
  background: 'rgba(0,0,0,0)',
};

const PanelStringHistogramInner: React.FC<
  PanelStringHistogramWeaveProps & {height: number; width: number}
> = props => {
  const weave = useWeaveContext();
  const table = define2DTable(
    {
      label: varNode('any', 'row') as any,
      value: opCount({
        arr: varNode('any', 'row') as any,
      }),
      source: props.input,
    },
    weave
  );
  const tableQuery = CGReact.useNodeValue(table.resultNode as any);
  if (tableQuery.loading) {
    return <Panel2Loader />;
  }
  return (
    <CustomPanelRenderer
      spec={BAR_CHART}
      loading={tableQuery.loading}
      slow={false}
      data={tableQuery.result}
      userSettings={{
        fieldSettings: {label: 'row', value: 'count'},
        stringSettings: {title: ''},
      }}
    />
  );
};

export const Spec: Panel2.PanelSpec = {
  hidden: true,
  id: 'string-histogram-weave',
  Component: PanelStringHistogramWeave,
  inputType,
  canFullscreen: true,
};
