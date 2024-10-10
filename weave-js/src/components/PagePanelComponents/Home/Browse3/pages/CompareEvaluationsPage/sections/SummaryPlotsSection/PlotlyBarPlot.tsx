import * as Plotly from 'plotly.js';
import React, {useEffect, useMemo, useRef} from 'react';

import {PLOT_GRID_COLOR} from '../../ecpConstants';

export const PlotlyBarPlot: React.FC<{
  height: number;
  plotlyData: Plotly.Data;
}> = props => {
  const divRef = useRef<HTMLDivElement>(null);
  const plotlyLayout: Partial<Plotly.Layout> = useMemo(() => {
    return {
      height: props.height - 40,
      showlegend: false,
      margin: {
        l: 0,
        r: 0,
        b: 20,
        t: 20,
        pad: 0,
      },
      xaxis: {
        automargin: true,
        fixedrange: true,
        gridcolor: PLOT_GRID_COLOR,
        linecolor: PLOT_GRID_COLOR,
      },
      yaxis: {
        fixedrange: true,
        gridcolor: PLOT_GRID_COLOR,
        linecolor: PLOT_GRID_COLOR,
      },
      title: {
        text: props.plotlyData.name ?? '',
        font: {size: 14},
        xref: 'paper',
        x: 0.5,
        y: 1, // Position at the top
        yanchor: 'top',
      },
    };
  }, [props.height, props.plotlyData]);

  const plotlyConfig = useMemo(() => {
    return {
      displayModeBar: false,
      responsive: true,
      staticPlot: true,
    };
  }, []);

  useEffect(() => {
    Plotly.newPlot(
      divRef.current as any,
      [props.plotlyData],
      plotlyLayout,
      plotlyConfig
    );
  }, [plotlyConfig, props.plotlyData, plotlyLayout]);

  return <div ref={divRef}></div>;
};
