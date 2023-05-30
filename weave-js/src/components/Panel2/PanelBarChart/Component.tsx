import CustomPanelRenderer from '@wandb/weave/common/components/Vega3/CustomPanelRenderer';
import _ from 'lodash';
import React, {useMemo} from 'react';
import {VisualizationSpec} from 'react-vega';

import * as CGReact from '../../../react';
import * as Panel2 from '../panel';
import {Panel2Loader} from '../PanelComp';
import {useColorNode} from '../panellib/libcolors';
import {inputType} from './common';

type PanelBarChartProps = Panel2.PanelProps<typeof inputType>;

/* eslint-disable no-template-curly-in-string */

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

const BAR_CHART_COLORED: VisualizationSpec = {
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
    color: {
      type: 'nominal',
      field: 'color',
      scale: {range: {field: 'color'}},
      legend: false as any,
    },
    opacity: {
      value: 1,
    },
  },
  background: 'rgba(0,0,0,0)',
};

const PanelBarChart: React.FC<PanelBarChartProps> = props => {
  const path = props.input;
  const colorNode = useColorNode(path);
  const isColorable = colorNode.nodeType !== 'void';
  const colorNodeValue = CGReact.useNodeValue(colorNode);
  const nodeValue = CGReact.useNodeValue<
    | {
        type: 'dict';
        objectType: {
          type: 'union';
          members: Array<'number' | 'none'>;
        };
        maxLength?: undefined;
      }
    | {
        type: 'list';
        maxLength: number;
        objectType: {
          type: 'union';
          members: Array<'number' | 'none'>;
        };
      }
  >(path);
  const data: Array<{[key: string]: any}> = useMemo(() => {
    if (nodeValue.result == null) {
      return [];
    }
    if (_.isArray(nodeValue.result)) {
      return nodeValue.result.map((item, ndx) => {
        const row: {[key: string]: any} = {key: '' + ndx, value: item ?? 0};
        if (isColorable) {
          row.color = colorNodeValue?.result?.[ndx] ?? '#94aecb';
        }
        return row;
      });
    } else {
      return Object.entries(nodeValue.result).map(([key, value]) => ({
        key,
        value,
      }));
    }
  }, [nodeValue, colorNodeValue, isColorable]);
  if (
    nodeValue.loading ||
    (colorNode.nodeType !== 'void' && colorNodeValue.loading)
  ) {
    return <Panel2Loader />;
  }

  if (data.length === 0) {
    return <></>;
  }
  return (
    <CustomPanelRenderer
      spec={isColorable ? BAR_CHART_COLORED : BAR_CHART}
      loading={nodeValue.loading}
      slow={false}
      data={data}
      userSettings={{
        fieldSettings: {label: 'key', value: 'value', color: 'color'},
        stringSettings: {title: ''},
      }}
    />
  );
};

export default PanelBarChart;
