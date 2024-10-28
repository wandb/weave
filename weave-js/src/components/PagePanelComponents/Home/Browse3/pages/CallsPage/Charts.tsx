import {quantile} from 'd3-array';
import _ from 'lodash';
import moment from 'moment';
import * as Plotly from 'plotly.js';
import React, {useEffect, useMemo, useRef} from 'react';

import {
  BLUE_500,
  GREEN_500,
  MOON_200,
  MOON_300,
  MOON_500,
  MOON_750,
  TEAL_400,
} from '../../../../../../common/css/color.styles';

type ChartDataRequests = {
  started_at: string;
};

type ChartDataErrors = {
  started_at: string;
  isError: boolean;
};

type ChartDataLatency = {
  started_at: string;
  latency: number;
};

const CHART_TITLE_STYLE = {
  font: {
    color: MOON_750,
    family: '"Source Sans Pro", sans-serif',
    size: 16,
    weight: 700,
  },
  pad: {
    l: 16,
  },
  x: 0,
  xanchor: 'left' as const,
};

const CHART_MARGIN_STYLE = {
  l: 50,
  r: 30,
  b: 50,
  t: 50,
  pad: 0,
};

const X_AXIS_STYLE: Partial<Plotly.LayoutAxis> = {
  type: 'date' as const,
  automargin: true,
  showgrid: false,
  linecolor: MOON_300,
  showspikes: true,
  spikemode: 'across',
  spikethickness: 1,
  spikecolor: MOON_300,
  tickfont: {color: MOON_500},
};

const Y_AXIS_STYLE: Partial<Plotly.LayoutAxis> = {
  automargin: true,
  griddash: 'dot',
  showgrid: true,
  gridcolor: MOON_300,
  linecolor: MOON_300,
  showspikes: false,
  tickfont: {color: MOON_500},
};

export const LatencyPlotlyChart: React.FC<{
  height: number;
  chartData: ChartDataLatency[];
  binSizeMinutes?: number;
}> = ({height, chartData, binSizeMinutes = 60}) => {
  const divRef = useRef<HTMLDivElement>(null);

  const plotlyData: Plotly.Data[] = useMemo(() => {
    const groupedData = _(chartData)
      .groupBy(d => {
        const date = moment(d.started_at);
        const roundedMinutes =
          Math.floor(date.minutes() / binSizeMinutes) * binSizeMinutes;
        return date.startOf('hour').add(roundedMinutes, 'minutes').format();
      })
      .map((group, date) => {
        const latenciesNonSorted = group.map(d => d.latency);
        const p50 = quantile(latenciesNonSorted, 0.5) ?? 0;
        const p95 = quantile(latenciesNonSorted, 0.95) ?? 0;
        const p99 = quantile(latenciesNonSorted, 0.99) ?? 0;
        return {timestamp: date, p50, p95, p99};
      })
      .value();

    return [
      {
        type: 'scatter',
        mode: 'lines+markers',
        x: groupedData.map(d => d.timestamp),
        y: groupedData.map(d => d.p50),
        name: 'p50 Latency',
        line: {color: BLUE_500},
        marker: {color: BLUE_500},
        hovertemplate: '%{data.name}: %{y:.2f} ms<extra></extra>',
      },
      {
        type: 'scatter',
        mode: 'lines+markers',
        x: groupedData.map(d => d.timestamp),
        y: groupedData.map(d => d.p95),
        name: 'p95 Latency',
        line: {color: GREEN_500},
        marker: {color: GREEN_500},
        hovertemplate: '%{data.name}: %{y:.2f} ms<extra></extra>',
      },
      {
        type: 'scatter',
        mode: 'lines+markers',
        x: groupedData.map(d => d.timestamp),
        y: groupedData.map(d => d.p99),
        name: 'p99 Latency',
        line: {color: MOON_500},
        marker: {color: MOON_500},
        hovertemplate: '%{data.name}: %{y:.2f} ms<extra></extra>',
      },
    ];
  }, [chartData, binSizeMinutes]);

  useEffect(() => {
    const plotlyLayout: Partial<Plotly.Layout> = {
      height: height - 40,
      title: {
        text: '<span style="font-weight: 600;">Latency</span>',
        ...CHART_TITLE_STYLE,
      },
      margin: CHART_MARGIN_STYLE,
      xaxis: X_AXIS_STYLE,
      yaxis: Y_AXIS_STYLE,
      hovermode: 'x unified',
      showlegend: false,
      hoverlabel: {
        bordercolor: MOON_200,
      },
    };

    const plotlyConfig: Partial<Plotly.Config> = {
      displayModeBar: false,
      responsive: true,
    };

    Plotly.newPlot(
      divRef.current as any,
      plotlyData,
      plotlyLayout,
      plotlyConfig
    );
  }, [plotlyData, height]);

  return <div ref={divRef}></div>;
};

export const ErrorPlotlyChart: React.FC<{
  height: number;
  chartData: ChartDataErrors[];
}> = ({height, chartData}) => {
  const divRef = useRef<HTMLDivElement>(null);

  const plotlyData: Plotly.Data[] = useMemo(() => {
    const errorData = chartData;

    return [
      {
        type: 'histogram',
        x: errorData.map(d => d.started_at),
        name: 'Error Count',
        marker: {color: TEAL_400},
        histfunc: 'count',
        hovertemplate: '%{y} errors<extra></extra>',
      },
    ];
  }, [chartData]);

  useEffect(() => {
    const plotlyLayout: Partial<Plotly.Layout> = {
      height: height - 40,
      title: {
        text: '<span style="font-weight: 600;">Errors</span>',
        ...CHART_TITLE_STYLE,
      },
      margin: CHART_MARGIN_STYLE,
      bargroupgap: 0.1,
      xaxis: X_AXIS_STYLE,
      yaxis: {...Y_AXIS_STYLE, zeroline: false},
      hovermode: 'x unified',
      hoverlabel: {
        bordercolor: MOON_200,
      },
      dragmode: 'zoom',
    };

    const plotlyConfig: Partial<Plotly.Config> = {
      displayModeBar: false,
      responsive: true,
    };

    Plotly.newPlot(
      divRef.current as any,
      plotlyData,
      plotlyLayout,
      plotlyConfig
    );
  }, [plotlyData, height]);

  return <div ref={divRef}></div>;
};

export const RequestsPlotlyChart: React.FC<{
  height: number;
  chartData: ChartDataRequests[];
}> = ({height, chartData}) => {
  const divRef = useRef<HTMLDivElement>(null);

  const plotlyData: Plotly.Data[] = useMemo(
    () => [
      {
        type: 'histogram',
        x: chartData.map(d => d.started_at),
        name: 'Requests',
        marker: {color: TEAL_400},
        hovertemplate: '%{y} requests<extra></extra>',
      },
    ],
    [chartData]
  );

  useEffect(() => {
    const plotlyLayout: Partial<Plotly.Layout> = {
      height: height - 40,
      title: {
        text: '<span style="font-weight: 600;">Requests</span>',
        ...CHART_TITLE_STYLE,
      },
      margin: CHART_MARGIN_STYLE,
      xaxis: X_AXIS_STYLE,
      yaxis: {...Y_AXIS_STYLE, zeroline: false},
      bargap: 0.2,
      hovermode: 'x unified',
      hoverlabel: {
        bordercolor: MOON_200,
      },
    };

    const plotlyConfig: Partial<Plotly.Config> = {
      displayModeBar: false,
      responsive: true,
    };

    Plotly.newPlot(
      divRef.current as any,
      plotlyData,
      plotlyLayout,
      plotlyConfig
    );
  }, [plotlyData, height]);

  return <div ref={divRef}></div>;
};
