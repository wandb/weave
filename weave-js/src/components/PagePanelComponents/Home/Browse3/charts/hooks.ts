import Plotly from 'plotly.js';
import {Data, Layout} from 'plotly.js';
import React, {useRef} from 'react';

import {
  ChartConfig,
  ChartDataPoint,
  LayoutGenerator,
  TimestampPoint,
  TraceGenerator,
} from './ChartTypes';
import {groupDataByMinBins, processTimestampData} from './utils';

/**
 * Custom hook for managing Plotly charts with standardized data processing
 */
export function usePlotlyChart<T extends TimestampPoint>(
  chartData: T[],
  config: ChartConfig,
  getTraceData: TraceGenerator,
  getCustomLayout: LayoutGenerator
) {
  const chartRef = useRef<HTMLDivElement>(null);
  const [xDomain, setXDomain] = React.useState<any[] | undefined>(
    config.xDomain
  );

  // Process data once
  const processedData = React.useMemo(() => {
    let data = processTimestampData(chartData);

    // For bar charts, apply minBins binning for the current xDomain (zoomed range)
    if (config.plotType === 'bar') {
      let filtered = data;
      if (xDomain && xDomain.length === 2) {
        const [min, max] = xDomain;
        filtered = data.filter(d => {
          const xVal = d.x instanceof Date ? d.x.getTime() : Number(d.x);
          const minVal = min instanceof Date ? min.getTime() : Number(min);
          const maxVal = max instanceof Date ? max.getTime() : Number(max);
          return xVal >= minVal && xVal <= maxVal;
        });
      }
      data = groupDataByMinBins(
        filtered,
        config.minBins ?? 10,
        config.aggregation ?? 'sum'
      );
    }

    return data;
  }, [chartData, config.plotType, config.minBins, config.aggregation, xDomain]);

  // Create the isTimeBasedX flag
  const isTimeBasedX = processedData.length > 0 && processedData[0].isTimeX;

  React.useEffect(() => {
    if (!chartRef.current || processedData.length === 0) return;

    const element = chartRef.current;
    const trace = getTraceData(processedData);
    const baseLayout = {height: config.height} as Partial<Layout>;
    const customLayout = getCustomLayout(baseLayout, processedData);

    Plotly.newPlot(element, [trace as Data], customLayout, {
      responsive: true,
      displayModeBar: false,
      showTips: false,
    });

    // Listen for zoom (relayout) events to update xDomain for bar charts
    const handleRelayout = (event: any) => {
      if (
        config.plotType === 'bar' &&
        event['xaxis.range[0]'] !== undefined &&
        event['xaxis.range[1]'] !== undefined
      ) {
        let min = event['xaxis.range[0]'];
        let max = event['xaxis.range[1]'];
        // Convert to Date if isTimeBasedX
        if (isTimeBasedX) {
          min = new Date(min);
          max = new Date(max);
        } else {
          min = Number(min);
          max = Number(max);
        }
        setXDomain([min, max]);
      } else if (
        config.plotType === 'bar' &&
        (event['xaxis.autorange'] ||
          (event['xaxis.range'] && event['xaxis.range'].length === 2))
      ) {
        // Reset to full domain if autorange
        setXDomain(undefined);
      }
    };
    // @ts-ignore
    element.on && element.on('plotly_relayout', handleRelayout);

    // Add window resize handler to update the plot
    const handleResize = () => {
      if (chartRef.current) {
        Plotly.relayout(element, {});
      }
    };
    window.addEventListener('resize', handleResize);

    return () => {
      window.removeEventListener('resize', handleResize);
      if (chartRef.current) {
        Plotly.purge(element);
        if ((element as any).removeAllListeners) {
          (element as any).removeAllListeners('plotly_relayout');
        }
      }
    };
  }, [processedData, config, getTraceData, getCustomLayout, isTimeBasedX]);

  return {
    chartRef,
    processedData,
    isTimeBasedX,
  };
}

/**
 * Creates a memoized trace data generator function
 */
export function useTraceGenerator(
  color: string,
  units?: string,
  customHoverTemplate?: string
): TraceGenerator {
  return React.useCallback(
    (processedData: ChartDataPoint[]) => {
      return {
        x: processedData.map(d => d.x),
        y: processedData.map(d => d.y),
        mode: 'markers' as const,
        type: 'scatter' as const,
        marker: {
          color,
          size: 5,
        },
        hovertemplate:
          customHoverTemplate ||
          `%{y} ${units || ''}<br>%{x|%b %d, %H:%M}<extra></extra>`,
      };
    },
    [color, units, customHoverTemplate]
  );
}

/**
 * Creates a memoized layout generator function
 */
export function useLayoutGenerator(
  title: string,
  xAxisTitle: string,
  yAxisTitle: string,
  xDomain?: any[],
  yDomain?: any[],
  isTimeBasedX: boolean = true
): LayoutGenerator {
  return React.useCallback(
    (baseLayout: Partial<Layout>) => {
      return {
        ...baseLayout,
        title,
        yaxis: {
          ...baseLayout.yaxis,
          title: yAxisTitle,
          range: yDomain || undefined,
        },
        xaxis: {
          ...baseLayout.xaxis,
          title: xAxisTitle,
          type: isTimeBasedX ? ('date' as const) : ('linear' as const),
          tickformat: isTimeBasedX ? '%H:%M' : ',.1f',
          range: xDomain || undefined,
        },
      };
    },
    [title, xAxisTitle, yAxisTitle, xDomain, yDomain, isTimeBasedX]
  );
}
