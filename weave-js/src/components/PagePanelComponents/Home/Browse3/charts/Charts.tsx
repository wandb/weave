import React from 'react';

import {BLUE_500, GREEN_500} from '../../../../../common/css/color.styles';
import {ChartDataPoint, TimestampPoint} from './ChartTypes';
import {usePlotlyChart} from './hooks';
import {getBaseLayout, groupDataByMinBins, processTimestampData} from './utils';

// Export the chart data types from the types file
export * from './ChartTypes';

export type HistogramPlotProps = {
  data: TimestampPoint[];
  height: number;
  xLabel: string;
  yLabel: string;
  color?: string;
  minBins?: number;
  aggregation?: 'sum' | 'avg' | 'count' | 'min' | 'max';
  tooltipTemplate?: string;
  xDomain?: any[];
  yDomain?: any[];
};

export const HistogramPlot: React.FC<HistogramPlotProps> = ({
  data,
  height,
  xLabel,
  yLabel,
  color = GREEN_500,
  minBins = 10,
  aggregation = 'sum',
  tooltipTemplate = '%{y}<br>Calls in bin: %{customdata[0]}<br>%{x|%b %d, %H:%M}<extra></extra>',
  xDomain,
  yDomain,
}) => {
  const getTraceData = React.useCallback(
    (processed: ChartDataPoint[]) => ({
      x: processed.map((d: ChartDataPoint) => d.x),
      y: processed.map((d: ChartDataPoint) => d.y),
      type: 'bar' as const,
      marker: {color},
      customdata: processed.map((d: ChartDataPoint) => [d.numCalls ?? 0]),
      hovertemplate: tooltipTemplate,
    }),
    [color, tooltipTemplate]
  );

  const getCustomLayout = React.useCallback(
    (baseLayout: any) => ({
      ...baseLayout,
      ...getBaseLayout(height),
      yaxis: {
        ...getBaseLayout(height).yaxis,
        title: yLabel,
        range: yDomain || undefined,
      },
      xaxis: {
        ...getBaseLayout(height).xaxis,
        title: xLabel,
        range: xDomain || undefined,
      },
    }),
    [xLabel, yLabel, xDomain, yDomain, height]
  );

  const config = {
    id: 'histogram',
    xAxis: xLabel,
    yAxis: yLabel,
    plotType: 'bar',
    height,
    minBins,
    aggregation,
    xDomain,
    yDomain,
  };

  const {chartRef} = usePlotlyChart(
    data,
    config,
    getTraceData,
    getCustomLayout
  );

  return (
    <div style={{position: 'relative', width: '100%', height: `${height}px`}}>
      <div ref={chartRef} style={{width: '100%', height: '100%'}} />
    </div>
  );
};

export type ScatterPlotProps = {
  data: TimestampPoint[];
  height: number;
  xLabel: string;
  yLabel: string;
  color?: string;
  tooltipTemplate?: string;
  xDomain?: any[];
  yDomain?: any[];
};

export const ScatterPlot: React.FC<ScatterPlotProps> = ({
  data,
  height,
  xLabel,
  yLabel,
  color = BLUE_500,
  tooltipTemplate = '%{y}<br>%{x|%b %d, %H:%M}<extra></extra>',
  xDomain,
  yDomain,
}) => {
  const getTraceData = React.useCallback(
    (processed: ChartDataPoint[]) => ({
      x: processed.map((d: ChartDataPoint) => d.x),
      y: processed.map((d: ChartDataPoint) => d.y),
      mode: 'markers' as const,
      type: 'scatter' as const,
      marker: {color, size: 5},
      hovertemplate: tooltipTemplate,
    }),
    [color, tooltipTemplate]
  );

  const getCustomLayout = React.useCallback(
    (baseLayout: any) => ({
      ...baseLayout,
      ...getBaseLayout(height),
      yaxis: {
        ...getBaseLayout(height).yaxis,
        title: yLabel,
        range: yDomain || undefined,
      },
      xaxis: {
        ...getBaseLayout(height).xaxis,
        title: xLabel,
        range: xDomain || undefined,
      },
    }),
    [xLabel, yLabel, xDomain, yDomain, height]
  );

  const config = {
    id: 'scatter',
    xAxis: xLabel,
    yAxis: yLabel,
    plotType: 'scatter',
    height,
    xDomain,
    yDomain,
  };

  const {chartRef} = usePlotlyChart(
    data,
    config,
    getTraceData,
    getCustomLayout
  );

  return (
    <div style={{position: 'relative', width: '100%', height: `${height}px`}}>
      <div ref={chartRef} style={{width: '100%', height: '100%'}} />
    </div>
  );
};

export type LinePlotProps = {
  data: TimestampPoint[];
  height: number;
  xLabel: string;
  yLabel: string;
  color?: string;
  aggregation?: 'sum' | 'avg' | 'count' | 'min' | 'max';
  minBins?: number;
  tooltipTemplate?: string;
  xDomain?: any[];
  yDomain?: any[];
};

export const LinePlot: React.FC<LinePlotProps> = ({
  data,
  height,
  xLabel,
  yLabel,
  color = BLUE_500,
  aggregation = 'sum',
  minBins = 10,
  tooltipTemplate = '%{y}<br>Calls in bin: %{customdata[0]}<br>%{x|%b %d, %H:%M}<extra></extra>',
  xDomain,
  yDomain,
}) => {
  const processedData = React.useMemo(() => {
    return groupDataByMinBins(processTimestampData(data), minBins, aggregation);
  }, [data, minBins, aggregation]);

  const getTraceData = React.useCallback(
    (processed: ChartDataPoint[]) => ({
      x: processed.map((d: ChartDataPoint) => d.x),
      y: processed.map((d: ChartDataPoint) => d.y),
      mode: 'lines' as const,
      type: 'scatter' as const,
      line: {color},
      customdata: processed.map((d: ChartDataPoint) => [d.numCalls ?? 0]),
      hovertemplate: tooltipTemplate,
    }),
    [color, tooltipTemplate]
  );

  const getCustomLayout = React.useCallback(
    (baseLayout: any) => ({
      ...baseLayout,
      ...getBaseLayout(height),
      yaxis: {
        ...getBaseLayout(height).yaxis,
        title: yLabel,
        range: yDomain || undefined,
      },
      xaxis: {
        ...getBaseLayout(height).xaxis,
        title: xLabel,
        range: xDomain || undefined,
      },
    }),
    [xLabel, yLabel, xDomain, yDomain, height]
  );

  const config = {
    id: 'line',
    xAxis: xLabel,
    yAxis: yLabel,
    plotType: 'line',
    height,
    minBins,
    aggregation,
    xDomain,
    yDomain,
  };

  const {chartRef} = usePlotlyChart(
    data,
    config,
    () => getTraceData(processedData),
    getCustomLayout
  );

  return (
    <div style={{position: 'relative', width: '100%', height: `${height}px`}}>
      <div ref={chartRef} style={{width: '100%', height: '100%'}} />
    </div>
  );
};
