import {callOpVeryUnsafe, constNodeUnsafe, Node} from '@wandb/weave/core';
import * as Plotly from 'plotly.js';
import React, {useEffect, useMemo, useRef} from 'react';

import {useNodeValue} from '../../../react';
import * as Panel2 from '../panel';
import {useUpdateConfig2} from '../PanelComp';
import {toWeaveType} from '../toWeaveType';

export const inputType = {type: 'Plotly'} as any;

interface PanelPlotlyConfig {
  selected?:
    | {
        xMin: number;
        xMax: number;
        yMin: number;
        yMax: number;
      }
    | Node;
}

type PanelPlotlyProps = Panel2.PanelProps<typeof inputType, PanelPlotlyConfig>;

export const PanelPlotly: React.FC<PanelPlotlyProps> = props => {
  const updateConfig2 = useUpdateConfig2(props);
  const jsonStringNode = useMemo(() => {
    return callOpVeryUnsafe('Plotly-contents', {self: props.input});
  }, [props.input]);
  const divRef = useRef<HTMLDivElement>(null);
  const result = useNodeValue(jsonStringNode as any);
  useEffect(() => {
    if (result.loading) {
      return;
    }
    const plotlySpec = JSON.parse(result.result);
    Plotly.newPlot(divRef.current as any, plotlySpec.data, plotlySpec.layout, {
      responsive: true,
    });
    (divRef.current as any).on('plotly_click', (data: any) => {
      console.log('PLOTLY CLICK', data);
    });
    (divRef.current as any).on('plotly_selected', (data: any) => {
      console.log('PLOTLY SELECTED', data);
      if (data?.range?.geo != null) {
        const geo = data.range.geo;
        // Note these are not really x&y, since we're selected in polar space
        const selection = {
          xMin: geo[0][0],
          xMax: geo[0][1],
          yMin: geo[1][0],
          yMax: geo[1][1],
        };
        console.log('SELECTED', selection);
        updateConfig2(() => ({
          selected: constNodeUnsafe(toWeaveType(selection), selection),
        }));
      } else if (data?.range != null) {
        const selection = {
          xMin: data.range.x[0],
          xMax: data.range.x[1],
          yMin: data.range.y[0],
          yMax: data.range.y[1],
        };
        updateConfig2(oldConfig => {
          console.log('PANEL PLOTLY CHANGE', oldConfig);
          return {
            selected: constNodeUnsafe(toWeaveType(selection), selection),
          };
        });
      }
    });
    // Purposely ignore loading here still.
    // TODO: Figure this out
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [result.result, updateConfig2]);
  return (
    <div
      data-test-weave-id="PanelPlotly"
      style={{width: '100%', height: '100%'}}
      ref={divRef}
    />
  );
};

export default PanelPlotly;
