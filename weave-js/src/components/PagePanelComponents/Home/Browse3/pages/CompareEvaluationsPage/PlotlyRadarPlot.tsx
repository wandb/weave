import * as Plotly from 'plotly.js';
import React, {useEffect, useMemo, useRef} from 'react';

import {MOON_300} from '../../../../../../common/css/color.styles';

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
  console.log(plotlyData);
  const plotlyLayout = useMemo(() => {
    return {
      height: props.height,
      showlegend: false,
      margin: {
        l: 30,
        r: 30,
        b: 30,
        t: 30,
        pad: 0,
      },
      polar: {
        color: MOON_300,
        radialaxis: {
          linecolor: MOON_300,
          visible: false,
          // range: [0, 50],
          gridcolor: MOON_300,
        },
        angularaxis: {
          linecolor: MOON_300,
          gridcolor: MOON_300,
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
