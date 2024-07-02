import * as Plotly from 'plotly.js';
import React, {useEffect, useMemo, useRef} from 'react';

import {MOON_300} from '../../../../../../common/css/color.styles';
import {RadarPlotData} from './PlotlyRadarPlot';

export const PlotlyBarPlot: React.FC<{
  height: number;
  data: RadarPlotData;
}> = props => {
  const divRef = useRef<HTMLDivElement>(null);
  const plotlyData: Plotly.Data[] = useMemo(() => {
    return Object.keys(props.data).map((key, i) => {
      const {metrics, name, color} = props.data[key];
      return {
        type: 'bar',
        y: Object.values(metrics),
        x: Object.keys(metrics),
        name,
        marker: {color},
      };
    });
  }, [props.data]);

  const plotlyLayout = useMemo(() => {
    return {
      height: props.height - 40,
      showlegend: false,
      margin: {
        l: 0,
        r: 0,
        b: 80,
        t: 0,
        pad: 0,
      },
      xaxis: {
        fixedrange: true,
        gridcolor: MOON_300,
        linecolor: MOON_300,
      },
      yaxis: {
        fixedrange: true,
        gridcolor: MOON_300,
        linecolor: MOON_300,
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
