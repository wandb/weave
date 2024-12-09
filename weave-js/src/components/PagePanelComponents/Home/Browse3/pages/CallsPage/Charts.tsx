import {quantile} from 'd3-array';
import _ from 'lodash';
import moment from 'moment';
import * as Plotly from 'plotly.js';
import React, {useMemo, useRef} from 'react';

import {
  BLUE_500,
  GREEN_500,
  MOON_200,
  MOON_300,
  MOON_500,
  RED_400,
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

const CHART_MARGIN_STYLE = {
  l: 50,
  r: 30,
  b: 50,
  t: 20,
  pad: 0,
};

const X_AXIS_STYLE: Partial<Plotly.LayoutAxis> = {
  type: 'date' as const,
  automargin: true,
  showgrid: false,
  linecolor: MOON_300,
  tickfont: {color: MOON_500},
  showspikes: false,
};

const X_AXIS_STYLE_WITH_SPIKES: Partial<Plotly.LayoutAxis> = {
  ...X_AXIS_STYLE,
  showspikes: true,
  spikemode: 'across',
  spikethickness: 1,
  spikecolor: MOON_300,
};

const Y_AXIS_STYLE: Partial<Plotly.LayoutAxis> = {
  automargin: true,
  griddash: 'dot',
  showgrid: true,
  gridcolor: MOON_300,
  linecolor: MOON_300,
  showspikes: false,
  tickfont: {color: MOON_500},
  zeroline: false,
};

const PLOT_DEBOUNCE_MS = 200;

export const calculateBinSize = (
  data: ChartDataLatency[] | ChartDataErrors[] | ChartDataRequests[],
  targetBinCount = 15
) => {
  if (data.length === 0) {
    return 60;
  } // default to 60 minutes if no data

  const startTime = moment(_.minBy(data, 'started_at')?.started_at);
  const endTime = moment(_.maxBy(data, 'started_at')?.started_at);

  const minutesInRange = endTime.diff(startTime, 'minutes');

  // Calculate bin size in minutes, rounded to a nice number
  const rawBinSize = Math.max(1, Math.ceil(minutesInRange / targetBinCount));
  const niceNumbers = [1, 2, 5, 10, 15, 30, 60, 120, 240, 360, 720, 1440];

  // Find the closest nice number
  return niceNumbers.reduce((prev, curr) => {
    return Math.abs(curr - rawBinSize) < Math.abs(prev - rawBinSize)
      ? curr
      : prev;
  }, niceNumbers[0]);
};

export const LatencyPlotlyChart: React.FC<{
  height: number;
  chartData: ChartDataLatency[];
  targetBinCount?: number;
}> = ({height, chartData, targetBinCount}) => {
  const divRef = useRef<HTMLDivElement>(null);
  const binSize = calculateBinSize(chartData, targetBinCount);

  const plotlyData: Plotly.Data[] = useMemo(() => {
    const groupedData = _(chartData)
      .groupBy(d => {
        const date = moment(d.started_at);
        const roundedMinutes = Math.floor(date.minutes() / binSize) * binSize;
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
  }, [chartData, binSize]);

  const plotlyLayout: Partial<Plotly.Layout> = {
    height,
    margin: CHART_MARGIN_STYLE,
    xaxis: X_AXIS_STYLE_WITH_SPIKES,
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

  if (divRef.current) {
    _.debounce(() => {
      Plotly.newPlot(divRef.current!, plotlyData, plotlyLayout, plotlyConfig);
    }, PLOT_DEBOUNCE_MS)();
  }

  return <div ref={divRef}></div>;
};

export const ErrorPlotlyChart: React.FC<{
  height: number;
  chartData: ChartDataErrors[];
  targetBinCount?: number;
}> = ({height, chartData, targetBinCount}) => {
  const divRef = useRef<HTMLDivElement>(null);
  const binSize = calculateBinSize(chartData, targetBinCount);

  const plotlyData: Plotly.Data[] = useMemo(() => {
    const groupedData = _(chartData)
      .groupBy(d => {
        const date = moment(d.started_at);
        const roundedMinutes = Math.floor(date.minutes() / binSize) * binSize;
        return date.startOf('hour').add(roundedMinutes, 'minutes').format();
      })
      .map((group, date) => ({
        timestamp: date,
        count: group.filter(d => d.isError).length,
      }))
      .value();

    return [
      {
        type: 'bar',
        x: groupedData.map(d => d.timestamp),
        y: groupedData.map(d => d.count),
        name: 'Error Count',
        marker: {color: RED_400},
        hovertemplate: '%{y} errors<extra></extra>',
      },
    ];
  }, [chartData, binSize]);

  const plotlyLayout: Partial<Plotly.Layout> = {
    height,
    margin: CHART_MARGIN_STYLE,
    bargap: 0.2,
    xaxis: X_AXIS_STYLE,
    yaxis: Y_AXIS_STYLE,
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

  if (divRef.current) {
    _.debounce(() => {
      Plotly.newPlot(divRef.current!, plotlyData, plotlyLayout, plotlyConfig);
    }, PLOT_DEBOUNCE_MS)();
  }

  return <div ref={divRef}></div>;
};

export const RequestsPlotlyChart: React.FC<{
  height: number;
  chartData: ChartDataRequests[];
  targetBinCount?: number;
}> = ({height, chartData, targetBinCount}) => {
  const divRef = useRef<HTMLDivElement>(null);
  const binSize = calculateBinSize(chartData, targetBinCount);

  const plotlyData: Plotly.Data[] = useMemo(() => {
    const groupedData = _(chartData)
      .groupBy(d => {
        const date = moment(d.started_at);
        const roundedMinutes = Math.floor(date.minutes() / binSize) * binSize;
        return date.startOf('hour').add(roundedMinutes, 'minutes').format();
      })
      .map((group, date) => ({
        timestamp: date,
        count: group.length,
      }))
      .value();

    return [
      {
        type: 'bar',
        x: groupedData.map(d => d.timestamp),
        y: groupedData.map(d => d.count),
        name: 'Requests',
        marker: {color: TEAL_400},
        hovertemplate: '%{y} requests<extra></extra>',
      },
    ];
  }, [chartData, binSize]);

  const plotlyLayout: Partial<Plotly.Layout> = {
    height,
    margin: CHART_MARGIN_STYLE,
    xaxis: X_AXIS_STYLE,
    yaxis: Y_AXIS_STYLE,
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

  if (divRef.current) {
    _.debounce(() => {
      Plotly.newPlot(divRef.current!, plotlyData, plotlyLayout, plotlyConfig);
    }, PLOT_DEBOUNCE_MS)();
  }

  return <div ref={divRef}></div>;
};
