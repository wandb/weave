import * as Plotly from 'plotly.js';
import React, {useEffect, useMemo, useRef} from 'react';

import {MOON_300} from '../../../../../../common/css/color.styles';

export type ScatterPlotData = Array<{x: number[]; y: number[]; color: string}>;
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

  const ranges = useMemo(() => {
    const x = props.data.map(s => s.x).flat();
    const y = props.data.map(s => s.y).flat();
    return {
      x: [Math.min(...x), Math.max(...x)],
      y: [Math.min(...y), Math.max(...y)],
    };
  }, [props.data]);

  const lowerBound = Math.min(ranges.x[0], ranges.y[0]);
  const upperBound = Math.min(ranges.x[1], ranges.y[1]);

  const plotlyLayout: Partial<Plotly.Layout> = useMemo(() => {
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
        // fixedrange: true,
        gridcolor: MOON_300,
        linecolor: MOON_300,
      },
      yaxis: {
        // fixedrange: true,
        gridcolor: MOON_300,
        linecolor: MOON_300,
      },
      shapes: [
        {
          type: 'line',
          x0: lowerBound,
          y0: lowerBound,
          x1: upperBound,
          y1: upperBound,
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
