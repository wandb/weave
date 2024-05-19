import CustomPanelRenderer from '@wandb/weave/common/components/Vega3/CustomPanelRenderer';
import React, {useMemo} from 'react';
import {useInView} from 'react-intersection-observer';
import {VisualizationSpec} from 'react-vega';
import {AutoSizer} from 'react-virtualized';

import {useGatedValue} from '../../hookUtils';
import * as CGReact from '../../react';
import * as Panel2 from './panel';
import {Panel2Loader} from './PanelComp';
import {useColorNode} from './panellib/libcolors';

const inputType = {
  type: 'list' as const,
  objectType: {
    type: 'union' as const,
    members: ['none' as const, 'string' as const],
  },
};

type PanelStringHistogramProps = Panel2.PanelProps<typeof inputType>;

/* eslint-disable no-template-curly-in-string */
const makeHistoSpec = (
  labelLimit: number,
  valueLimit: number = 100
): VisualizationSpec => ({
  $schema: 'https://vega.github.io/schema/vega-lite/v4.json',
  description: 'A simple histogram',
  data: {
    name: 'wandb',
  },
  transform: [
    {
      aggregate: [
        {
          op: 'count',
          as: 'value_count',
        },
      ],
      groupby: ['value'],
    },
    {
      window: [{op: 'row_number', as: 'value_rank'}],
      sort: [
        {
          field: 'value_count',
          order: 'descending',
        },
      ],
    },
    {filter: `datum.value_rank < ${valueLimit}`},
  ],
  title: '${string:title}',
  mark: {type: 'bar', tooltip: {content: 'data'}},
  encoding: {
    y: {
      type: 'nominal',
      field: 'value',
      axis: {
        title: null,
        labelLimit,
      },
      sort: {field: 'value_count', order: 'descending'},
    },
    x: {
      field: 'value_count',
      type: 'quantitative',
    },
    opacity: {value: 0.7},
  },
  background: 'rgba(0,0,0,0)',
});

const makeHistoSpecColored = (
  labelLimit: number,
  valueLimit: number = 100
): VisualizationSpec => ({
  $schema: 'https://vega.github.io/schema/vega-lite/v4.json',
  description: 'A simple histogram',
  data: {
    name: 'wandb',
  },
  transform: [
    {
      aggregate: [
        {
          op: 'count',
          as: 'value_count',
        },
      ],
      groupby: ['value', 'color'],
    },
    {
      window: [{op: 'row_number', as: 'value_rank'}],
      sort: [
        {
          field: 'value_count',
          order: 'descending',
        },
      ],
    },
    {filter: `datum.value_rank < ${valueLimit}`},
  ],
  title: '${string:title}',
  mark: {type: 'bar', tooltip: {content: 'data'}},
  encoding: {
    y: {
      type: 'nominal',
      field: 'value',
      axis: {
        title: null,
        labelLimit,
      },
      sort: {field: 'value_count', order: 'descending'},
    },
    x: {
      field: 'value_count',
      type: 'quantitative',
    },
    color: {
      type: 'nominal',
      field: 'color',
      legend: false as any,
      scale: {range: {field: 'color'}},
    },
    opacity: {
      value: 1,
    },
  },
  background: 'rgba(0,0,0,0)',
});

const PanelStringHistogram: React.FC<PanelStringHistogramProps> = props => {
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

const PanelStringHistogramInner: React.FC<
  PanelStringHistogramProps & {height: number; width: number}
> = props => {
  const labelLimit = Math.max(20, (props.width - 50) / 3);
  const valueLimit = Math.floor(Math.max(3, (props.height - 35) / 7));
  const colorNode = useColorNode(props.input);
  const colorNodeValue = CGReact.useNodeValue(colorNode);
  const isColorable = colorNode.nodeType !== 'void';
  const nodeValueQuery = CGReact.useNodeValue(props.input);
  const data = useMemo(() => {
    if (nodeValueQuery.loading || (isColorable && colorNodeValue.loading)) {
      return [];
    }
    if (!isColorable) {
      return nodeValueQuery.result.map(v => ({
        value: v,
      }));
    } else {
      return nodeValueQuery.result.map((v, ndx) => ({
        value: v,
        color: colorNodeValue.result[ndx] ?? '#94aecb',
      }));
    }
  }, [nodeValueQuery, isColorable, colorNodeValue]);
  const spec = useMemo(() => {
    return isColorable
      ? makeHistoSpecColored(labelLimit, valueLimit)
      : makeHistoSpec(labelLimit, valueLimit);
  }, [labelLimit, valueLimit, isColorable]);
  return useGatedValue(
    <>
      {nodeValueQuery.loading ? (
        <Panel2Loader />
      ) : (
        <CustomPanelRenderer
          spec={spec}
          loading={false}
          slow={false}
          data={data}
          userSettings={{fieldSettings: {}, stringSettings: {title: ''}}}
        />
      )}
    </>,
    x => !nodeValueQuery.loading
  );
};

export const Spec: Panel2.PanelSpec = {
  id: 'string-histogram',
  icon: 'chart-horizontal-bars',
  category: 'Data',
  Component: PanelStringHistogram,
  inputType,
  canFullscreen: true,
};
