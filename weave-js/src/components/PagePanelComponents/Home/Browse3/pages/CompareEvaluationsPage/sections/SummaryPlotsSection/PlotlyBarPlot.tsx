import * as Plotly from 'plotly.js';
import React, { useEffect, useMemo, useRef } from 'react';

import { PLOT_GRID_COLOR } from '../../ecpConstants';
import { RadarPlotData } from './PlotlyRadarPlot';

const truncateTitle = (title: string, maxLength: number = 20) => {
  if (title.length <= maxLength) return title;
  return title.slice(0, maxLength - 3) + '...';
};

export const PlotlyBarPlot: React.FC<{
  height: number;
  width: number;
  data: RadarPlotData;
  metric: string;
}> = props => {
  const divRef = useRef<HTMLDivElement>(null);

  const plotlyData: Plotly.Data[] = useMemo(() => {
    return Object.keys(props.data).map(key => {
      const { metrics, name, color } = props.data[key];
      return {
        type: 'bar',
        y: [metrics[props.metric]],
        x: [name],
        name,
        marker: { color },
        text: [name], // Add the name as text on the bar
        textposition: 'inside', // Position the text inside the bar
      };
    });
  }, [props.data, props.metric]);

  const plotlyLayout: Partial<Plotly.Layout> = useMemo(() => {
    return {
      width: props.width,
      height: props.height,
      showlegend: false,
      margin: { l: 50, r: 20, b: 20, t: 70, pad: 4 },
      xaxis: {
        showticklabels: false, // Hide x-axis labels
        showgrid: false, // Hide x-axis grid
        zeroline: false, // Hide x-axis zero line
      },
      yaxis: {
        fixedrange: true,
        gridcolor: PLOT_GRID_COLOR,
        linecolor: PLOT_GRID_COLOR,
        range: [0, 1], // Assuming normalized values
      },
      title: {
        text: truncateTitle(props.metric),
        font: {
          size: 14,
          color: '#333',
        },
        xref: 'paper',
        x: 0.5,
        xanchor: 'center',
        y: 0.95,
        yanchor: 'top',
      },
      bargap: 0.3, // Adjust the gap between bars
    };
  }, [props.width, props.height, props.metric]);

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
      plotlyData,
      plotlyLayout,
      plotlyConfig
    );
  }, [plotlyConfig, plotlyData, plotlyLayout]);

  return <div ref={divRef} style={{ height: '100%' }}></div>;
};
