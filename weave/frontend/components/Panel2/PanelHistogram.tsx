import React from 'react';
import {useMemo} from 'react';
import {VisualizationSpec} from 'react-vega';
import {useInView} from 'react-intersection-observer';

import CustomPanelRenderer from '@wandb/common/components/Vega3/CustomPanelRenderer';
import * as Panel2 from './panel';
import * as CGReact from '@wandb/common/cgreact';
import {useColorNode} from './panellib/libcolors';
import {useGatedValue} from '@wandb/common/state/hooks';

const inputType = {
  type: 'list' as const,
  objectType: {
    type: 'union' as const,
    members: ['none' as const, 'number' as const],
  },
};

type PanelHistogramProps = Panel2.PanelProps<typeof inputType>;

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
      bin: {maxbins: 10},
      type: 'quantitative',
      field: '${field:value}',
      axis: {
        title: null,
      },
    },
    y: {
      aggregate: 'count',
      stack: null,
      axis: {
        title: null,
      },
    },
    opacity: {value: 0.7},
  },
  background: 'rgba(0,0,0,0)',
  width: 'container',
  height: 'container',
  autosize: {type: 'fit', contains: 'content'},
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
      bin: {maxbins: 10},
      type: 'quantitative',
      field: '${field:value}',
      axis: {
        title: null,
      },
    },
    y: {
      aggregate: 'count',
      stack: true,
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
    opacity: {
      value: 1,
    },
  },
  background: 'rgba(0,0,0,0)',
};

const PanelHistogram: React.FC<PanelHistogramProps> = props => {
  const colorNode = useColorNode(props.input);
  const colorNodeValue = CGReact.useNodeValue(colorNode);
  const isColorable = colorNode.nodeType !== 'void';

  const {ref, inView} = useInView();
  const hasBeenOnScreen = useGatedValue(inView, o => o);
  const nodeValueQuery = CGReact.useNodeValue(props.input);
  const data = useMemo(() => {
    if (nodeValueQuery.loading || (isColorable && colorNodeValue.loading)) {
      return [];
    }
    if (!isColorable) {
      return nodeValueQuery.result.map(num => ({value: num}));
    } else {
      return nodeValueQuery.result.map((num, ndx) => ({
        value: num,
        color: colorNodeValue.result[ndx] ?? '#94aecb',
      }));
    }
  }, [nodeValueQuery, isColorable, colorNodeValue]);
  if (data.length === 0) {
    return <>-</>;
  }

  return (
    <div ref={ref} style={{width: '100%', height: '100%'}}>
      {!nodeValueQuery.loading && hasBeenOnScreen ? (
        <CustomPanelRenderer
          spec={isColorable ? HISTO_SPEC_COLORED : HISTO_SPEC}
          loading={false}
          slow={false}
          data={data}
          userSettings={{
            fieldSettings: {value: 'value'},
            stringSettings: {title: ''},
          }}
        />
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

export const Spec: Panel2.PanelSpec = {
  id: 'histogram',
  Component: PanelHistogram,
  inputType,
  canFullscreen: true,
};
