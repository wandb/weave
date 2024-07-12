import * as Plotly from 'plotly.js';
import React, {useEffect, useMemo, useRef} from 'react';

import {PLOT_GRID_COLOR} from '../../ecpConstants';

export type RadarPlotData = {
  [seriesId: string]: {
    metrics: {[metric: string]: number};
    name: string;
    color: string;
  };
};

export const PlotlyRadarPlot: React.FC<{
  height: number;
  data: RadarPlotData;
}> = props => {
  const divRef = useRef<HTMLDivElement>(null);
  const plotlyData: Plotly.Data[] = useMemo(() => {
    return Object.keys(props.data).map((key, i) => {
      const {metrics, name, color} = props.data[key];
      return {
        type: 'scatterpolar',
        r: Object.values(metrics),
        theta: Object.keys(metrics),
        fill: 'toself',
        name,
        marker: {color},
      };
    });
  }, [props.data]);
  const plotlyLayout: Partial<Plotly.Layout> = useMemo(() => {
    return {
      height: props.height,
      showlegend: false,
      margin: {
        l: 60,
        r: 0,
        b: 30,
        t: 30,
        pad: 0,
      },
      polar: {
        color: PLOT_GRID_COLOR,
        radialaxis: {
          linecolor: PLOT_GRID_COLOR,
          visible: false,
          gridcolor: PLOT_GRID_COLOR,
        },
        angularaxis: {
          linecolor: PLOT_GRID_COLOR,
          gridcolor: PLOT_GRID_COLOR,
          ticklen: 3,
        },
      },
    };
  }, [props.height]);
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

  return <div ref={divRef}></div>;
};
