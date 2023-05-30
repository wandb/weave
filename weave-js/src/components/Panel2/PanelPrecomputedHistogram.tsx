import CustomPanelRenderer from '@wandb/weave/common/components/Vega3/CustomPanelRenderer';
import React, {useMemo} from 'react';
import {useInView} from 'react-intersection-observer';
import {VisualizationSpec} from 'react-vega';

import {useGatedValue} from '../../hookUtils';
import {useNodeValue} from '../../react';
import {PanelProps} from './panel';
import * as Panel2 from './panel';
import {Panel2Loader} from './PanelComp';
import {useColorNode} from './panellib/libcolors';

/* eslint-disable no-template-curly-in-string */

export const inputType = {
  type: 'union' as const,
  members: ['histogram' as const, 'none' as const],
};

export type PanelPrecomputedHistogramProps = PanelProps<typeof inputType>;

export function getPrecomputedHistogramSpec(
  isColorable: boolean
): VisualizationSpec {
  return {
    $schema: 'https://vega.github.io/schema/vega-lite/v5.json',
    description: 'A simple histogram',
    data: {
      name: 'wandb',
    },
    title: '${string:title}',
    mark: {type: 'bar', tooltip: {content: 'data'}},
    encoding: {
      x: {
        type: 'quantitative',
        field: '${field:start}',
        axis: {
          title: null,
        },
      },
      x2: {
        field: '${field:end}',
      },
      y: {
        type: 'quantitative',
        field: '${field:count}',
        axis: {
          title: null,
        },
      },
      ...(isColorable
        ? {
            color: {
              type: 'nominal',
              field: 'color',
              legend: false as any,
              scale: {range: {field: 'color'}},
            },
          }
        : {}),
      opacity: {value: isColorable ? 0.7 : 1.0},
    },
    background: 'rgba(0,0,0,0)',
    width: 'container',
    height: 'container',
    autosize: {type: 'fit', contains: 'content'},
  };
}

// A panel that renders a histogram pre-computed server-side
const PanelPrecomputedHistogram: React.FC<
  PanelPrecomputedHistogramProps
> = props => {
  const colorNode = useColorNode(props.input);
  const colorNodeValue = useNodeValue(colorNode);
  const isColorable = colorNode.nodeType !== 'void';

  const {ref, inView} = useInView();
  const hasBeenOnScreen = useGatedValue(inView, o => o);
  const nodeValueQuery = useNodeValue(props.input);
  const data = useMemo(() => {
    if (
      nodeValueQuery.loading ||
      (isColorable && colorNodeValue.loading) ||
      nodeValueQuery.result == null
    ) {
      return [];
    }
    if (!isColorable) {
      return nodeValueQuery.result.values.map((num, ndx) => ({
        count: num,
        start: nodeValueQuery.result!.bins[ndx],
        end: nodeValueQuery.result!.bins[ndx + 1],
      }));
    } else {
      return nodeValueQuery.result.values.map((num, ndx) => ({
        count: num,
        start: nodeValueQuery.result!.bins[ndx],
        end: nodeValueQuery.result!.bins[ndx + 1],
        color: colorNodeValue.result[ndx] ?? '#94aecb',
      }));
    }
  }, [nodeValueQuery, isColorable, colorNodeValue]);

  if (nodeValueQuery.loading) {
    return <Panel2Loader />;
  }

  if (data.length === 0) {
    return <>-</>;
  }

  return (
    <div ref={ref} style={{width: '100%', height: '100%'}}>
      {!nodeValueQuery.loading && hasBeenOnScreen ? (
        <CustomPanelRenderer
          spec={getPrecomputedHistogramSpec(isColorable)}
          loading={false}
          slow={false}
          data={data}
          userSettings={{
            fieldSettings: {count: 'count', start: 'start', end: 'end'},
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
  id: 'precomputed-histogram',
  Component: PanelPrecomputedHistogram,
  inputType,
  canFullscreen: true,
};

export default Spec;
