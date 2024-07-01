import * as Plotly from 'plotly.js';
import React, {useEffect, useMemo, useRef} from 'react';

import {MOON_300} from '../../../../../../common/css/color.styles';

export type ScatterPlotData = {x: number[]; y: number[]; color: string}[];
export const PlotlyScatterPlot: React.FC<{
  height: number;
  data: ScatterPlotData;
}> = props => {
  const divRef = useRef<HTMLDivElement>(null);
  const plotlyData: Plotly.Data[] = useMemo(() => {
    return props.data.map(s => ({
      x: s.x,
      y: s.y,
      mode: 'markers',
      type: 'scatter',
      marker: {color: s.color, size: 12},
    }));
  }, [props.data]);

  const plotlyLayout = useMemo(() => {
    return {
      height: props.height,
      showlegend: false,
      margin: {
        l: 20, // legend
        r: 0,
        b: 30, // legend
        t: 0,
        pad: 0,
      },
      xaxis: {
        gridcolor: MOON_300,
        linecolor: MOON_300,
      },
      yaxis: {
        gridcolor: MOON_300,
        linecolor: MOON_300,
      },
      shapes: [
        {
          type: 'line',
          x0: 0,
          y0: 0,
          x1: 1,
          y1: 1,
          xref: 'paper',
          yref: 'paper',
          line: {
            color: 'rgba(50, 171, 96, 1)',
            width: 2,
            dash: 'dot',
          },
        },
      ],
    };
  }, [props.height]);
  const plotlyConfig = useMemo(() => {
    return {
      displayModeBar: false,
      responsive: true,
    };
  }, []);

  useEffect(() => {
    Plotly.newPlot(
      divRef.current as any,
      plotlyData,
      plotlyLayout,
      plotlyConfig
    );
  }, [plotlyConfig, plotlyData, plotlyLayout]);

  return <div ref={divRef}></div>;
};
