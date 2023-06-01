import CustomPanelRenderer from '@wandb/weave/common/components/Vega3/CustomPanelRenderer';
import _ from 'lodash';
import React, {useMemo} from 'react';
import {useInView} from 'react-intersection-observer';
import {VisualizationSpec} from 'react-vega';
import {AutoSizer} from 'react-virtualized';

import {useGatedValue} from '../../hookUtils';
import * as CGReact from '../../react';
import * as Panel2 from './panel';
import {useColorNode} from './panellib/libcolors';

const inputType = {
  type: 'list' as const,
  objectType: {
    type: 'union' as const,
    members: [
      'none' as const,
      {
        type: 'dict' as const,
        objectType: {
          type: 'union' as const,
          members: ['none' as const, 'string' as const],
        },
      },
      {
        type: 'list' as const,
        maxLength: 10,
        objectType: {
          type: 'union' as const,
          members: ['none' as const, 'string' as const],
        },
      },
    ],
  },
};

type PanelMultiStringHistogramProps = Panel2.PanelProps<typeof inputType>;

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
      groupby: ['name', 'value'],
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
    color: {
      field: 'name',
      title: null,
    },
    x: {
      field: 'value_count',
      stack: null,
      type: 'quantitative',
    },
    opacity: {value: 0.7},
    order: {
      field: 'name',
    },
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
      groupby: ['name', 'value', 'color'],
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
    color: {
      type: 'nominal',
      field: 'color',
      legend: false as any,
      scale: {range: {field: 'color'}},
    },
    x: {
      field: 'value_count',
      stack: true,
      type: 'quantitative',
    },
    opacity: {value: 1},
    order: {
      field: 'name',
    },
  },
  background: 'rgba(0,0,0,0)',
});

const PanelMultiStringHistogram: React.FC<
  PanelMultiStringHistogramProps
> = props => {
  const {ref, inView} = useInView();
  const hasBeenOnScreen = useGatedValue(inView, o => o);
  return (
    <div ref={ref} style={{width: '100%', height: '100%'}}>
      {hasBeenOnScreen ? (
        <AutoSizer style={{width: '100%', height: '100%'}}>
          {({width, height}) => (
            <PanelMultiStringHistogramInner
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

const PanelMultiStringHistogramInner: React.FC<
  PanelMultiStringHistogramProps & {height: number; width: number}
> = props => {
  const labelLimit = Math.max(20, (props.width - 50) / 3);
  const valueLimit = Math.floor(Math.max(3, (props.height - 35) / 7));
  const colorNode = useColorNode(props.input);
  const colorNodeValue = CGReact.useNodeValue(colorNode);
  const isColorable = colorNode.nodeType !== 'void';

  const nodeValueQuery = CGReact.useNodeValue(props.input);
  const data = useMemo(() => {
    const rows = nodeValueQuery.result;
    if (nodeValueQuery.loading || (isColorable && colorNodeValue.loading)) {
      return [];
    }
    const result: Array<{
      name: string;
      value: string | null;
      color?: string;
    }> = [];
    for (let i = 0; i < rows.length; i++) {
      const row = rows[i];
      if (row == null) {
        // pass
      } else if (_.isArray(row)) {
        row.forEach((item, ndx) => {
          if (item != null) {
            if (!isColorable) {
              result.push({name: '' + ndx, value: item});
            } else {
              result.push({
                name: colorNodeValue.result[i][ndx] ?? '#94aecb',
                value: item,
                color: colorNodeValue.result[i][ndx] ?? '#94aecb',
              });
            }
          }
        });
      } else {
        for (const [key, value] of Object.entries(row)) {
          result.push({name: key, value});
        }
      }
    }
    return result;
  }, [
    nodeValueQuery.loading,
    nodeValueQuery.result,
    isColorable,
    colorNodeValue,
  ]);
  const spec = useMemo(() => {
    return isColorable
      ? makeHistoSpecColored(labelLimit, valueLimit)
      : makeHistoSpec(labelLimit, valueLimit);
  }, [labelLimit, valueLimit, isColorable]);
  return (
    <CustomPanelRenderer
      spec={spec}
      loading={nodeValueQuery.loading}
      slow={false}
      data={data}
      userSettings={{fieldSettings: {}, stringSettings: {title: ''}}}
    />
  );
};

export const Spec: Panel2.PanelSpec = {
  id: 'multi-string-histogram',
  Component: PanelMultiStringHistogram,
  inputType,
  canFullscreen: true,
};
