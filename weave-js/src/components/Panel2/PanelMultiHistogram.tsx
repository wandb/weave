import CustomPanelRenderer from '@wandb/weave/common/components/Vega3/CustomPanelRenderer';
import _ from 'lodash';
import React, {useMemo} from 'react';
import {VisualizationSpec} from 'react-vega';

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
          members: ['none' as const, 'number' as const],
        },
      },
      {
        type: 'list' as const,
        maxLength: 10,
        objectType: {
          type: 'union' as const,
          members: ['none' as const, 'number' as const],
        },
      },
    ],
  },
};

type PanelMultiHistogramProps = Panel2.PanelProps<typeof inputType>;

/* eslint-disable no-template-curly-in-string */

const HISTO_SPEC: VisualizationSpec = {
  $schema: 'https://vega.github.io/schema/vega-lite/v4.json',
  description: 'A simple histogram',
  data: {
    name: 'wandb',
  },
  title: '${string:title}',
  mark: {type: 'bar', tooltip: {content: 'data'}},
  encoding: {
    x: {
      bin: true,
      type: 'quantitative',
      field: 'value',
      axis: {
        title: null,
      },
    },
    color: {
      field: 'name',
      title: null,
    },
    y: {
      aggregate: 'count',
      stack: null,
      axis: {
        title: null,
      },
    },
    opacity: {value: 0.7},
    order: {
      field: 'name',
    },
  },
  background: 'rgba(0,0,0,0)',
};

const HISTO_SPEC_COLORED: VisualizationSpec = {
  $schema: 'https://vega.github.io/schema/vega-lite/v4.json',
  description: 'A simple histogram',
  data: {
    name: 'wandb',
  },
  title: '${string:title}',
  mark: {type: 'bar', tooltip: {content: 'data'}},
  encoding: {
    x: {
      bin: true,
      type: 'quantitative',
      field: 'value',
      axis: {
        title: null,
      },
    },
    color: {
      type: 'nominal',
      field: 'color',
      legend: false as any,
      scale: {range: {field: 'color'}},
    },
    y: {
      aggregate: 'count',
      stack: true,
      axis: {
        title: null,
      },
    },
    opacity: {value: 1},
    order: {
      field: 'name',
    },
  },
  background: 'rgba(0,0,0,0)',
};

const PanelMultiHistogram: React.FC<PanelMultiHistogramProps> = props => {
  const colorNode = useColorNode(props.input);
  const colorNodeValue = CGReact.useNodeValue(colorNode);
  const isColorable = colorNode.nodeType !== 'void';

  const nodeValueQuery = CGReact.useNodeValue(props.input);
  const data = useMemo(() => {
    const rows = nodeValueQuery?.result ?? [];
    if (nodeValueQuery.loading || colorNodeValue.loading) {
      return [];
    }
    const result: Array<{
      name: string;
      value: number | null;
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
              result.push({name: '' + ndx, value: item ?? 0});
            } else {
              result.push({
                name: colorNodeValue.result[i][ndx] ?? '#94aecb',
                value: item ?? 0,
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
  }, [nodeValueQuery, isColorable, colorNodeValue]);
  if (data.length === 0) {
    return <>-</>;
  }

  return (
    <div style={{width: '100%', height: '100%'}}>
      <CustomPanelRenderer
        spec={isColorable ? HISTO_SPEC_COLORED : HISTO_SPEC}
        loading={false}
        slow={false}
        data={data}
        userSettings={{fieldSettings: {}, stringSettings: {title: ''}}}
      />
    </div>
  );
};

export const Spec: Panel2.PanelSpec = {
  id: 'multi-histogram',
  displayName: 'MultiHistogram',
  Component: PanelMultiHistogram,
  inputType,
  canFullscreen: true,
};
