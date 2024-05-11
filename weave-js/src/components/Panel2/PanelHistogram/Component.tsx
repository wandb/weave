import CustomPanelRenderer from '@wandb/weave/common/components/Vega3/CustomPanelRenderer';
import React, {useMemo} from 'react';
import {useInView} from 'react-intersection-observer';
import {VisualizationSpec} from 'react-vega';
import {BinParams} from 'vega-lite/build/src/bin';

import {useGatedValue} from '../../../hookUtils';
import {useNodeValue} from '../../../react';
import {useColorNode} from '../panellib/libcolors';
import {
  defaultConfig,
  Extent,
  HistogramConfig,
  PanelHistogramProps,
  useExtentFromData,
} from './common';

/* eslint-disable no-template-curly-in-string */

function getBinConfig(
  config: HistogramConfig,
  extentFromData: Extent
): BinParams {
  const min = config.extent?.[0] ?? extentFromData[0];
  const max = config.extent?.[1] ?? extentFromData[1];
  const extent: BinParams['extent'] =
    min != null && max != null ? [min, max] : undefined;

  const range = (max ?? 1) - (min ?? 1);

  const binConfig: BinParams = {extent};
  if (config.mode === 'bin-size') {
    binConfig.step = config.binSize ?? range / 10;
  } else if (config.mode === 'num-bins') {
    binConfig.step = range / (config.nBins ?? 10);
  }

  return binConfig;
}

function getVegaHistoSpec(
  config: HistogramConfig,
  isColorable: boolean,
  extent: Extent
): VisualizationSpec {
  return {
    $schema: 'https://vega.github.io/schema/vega-lite/v4.json',
    description: 'A simple histogram',
    data: {
      name: 'wandb',
    },
    title: '${string:title}',
    mark: {type: 'bar', tooltip: {content: 'data'}},
    encoding: {
      x: {
        bin: getBinConfig(config, extent),
        type: 'quantitative',
        field: '${field:value}',
        axis: {
          title: null,
        },
      },
      y: {
        aggregate: 'count',
        stack: isColorable ? true : null,
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

const PanelHistogram: React.FC<PanelHistogramProps> = props => {
  const config = props.config ?? defaultConfig();
  const colorNode = useColorNode(props.input);
  const colorNodeValue = useNodeValue(colorNode);
  const isColorable = colorNode.nodeType !== 'void';

  const {ref, inView} = useInView();
  const hasBeenOnScreen = useGatedValue(inView, o => o);
  const nodeValueQuery = useNodeValue(props.input);
  const data = useMemo(() => {
    if (nodeValueQuery.loading || (isColorable && colorNodeValue.loading)) {
      return [];
    }
    if (!isColorable) {
      return nodeValueQuery.result?.map(num => ({value: num})) || [];
    } else {
      return (
        nodeValueQuery.result?.map((num, ndx) => ({
          value: num,
          color: colorNodeValue.result[ndx] ?? '#94aecb',
        })) || []
      );
    }
  }, [nodeValueQuery, isColorable, colorNodeValue]);

  const dataExtent = useExtentFromData(props.input);

  if (data.length === 0) {
    return <>-</>;
  }

  return (
    <div ref={ref} style={{width: '100%', height: '100%'}}>
      {!nodeValueQuery.loading && hasBeenOnScreen ? (
        <CustomPanelRenderer
          spec={getVegaHistoSpec(config, isColorable, dataExtent)}
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

export default PanelHistogram;
