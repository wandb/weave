import {Box} from '@material-ui/core';
import {Alert} from '@mui/material';
import {Tailwind} from '@wandb/weave/components/Tailwind';
import React, {useEffect, useMemo, useRef, useState} from 'react';

import {Button} from '../../../../../../../Button';
import {
  BOX_RADIUS,
  PLOT_HEIGHT,
  PLOT_PADDING,
  STANDARD_BORDER,
  STANDARD_PADDING,
} from '../../ecpConstants';
import {EvaluationComparisonState} from '../../ecpState';
import {HorizontalBox, VerticalBox} from '../../Layout';
import {MetricsSelector} from '../SummaryPlotsSection/MetricsSelector';
import {PlotlyBarPlot} from '../SummaryPlotsSection/PlotlyBarPlot';
import {
  PlotlyRadarPlot,
  RadarPlotData,
} from '../SummaryPlotsSection/PlotlyRadarPlot';

// Helper function to extract metrics from a summarize call
export const getMetricsFromCall = (call: {
  callId: string;
  traceCall: any;
}): Record<string, number> | null => {
  if (!call || !call.traceCall) return null;

  const resultObj = call.traceCall?.result_obj;
  const output = call.traceCall?.output;
  const inputs = call.traceCall?.inputs || {};

  // Try various paths where metrics might be stored
  const potentialMetricsObjects = [
    output, // Direct output
    resultObj, // Direct result object
    resultObj?.metrics, // Common pattern: {metrics: {...}}
    resultObj?.summary, // Common pattern: {summary: {...}}
    resultObj?.result, // Common pattern: {result: {...}}
    inputs?.summary, // Sometimes the summary is in the inputs
  ];

  // Find first object with numeric metrics
  for (const metricsObj of potentialMetricsObjects) {
    if (metricsObj && typeof metricsObj === 'object') {
      const metrics: Record<string, number> = {};
      let hasNumericMetrics = false;

      Object.entries(metricsObj).forEach(([key, value]) => {
        if (typeof value === 'number') {
          metrics[key] = value;
          hasNumericMetrics = true;
        }
      });

      if (hasNumericMetrics) {
        return metrics;
      }
    }
  }

  return null;
};

interface SummarizePlotsProps {
  summarizeCalls: Array<{callId: string; traceCall: any}>;
  state: EvaluationComparisonState;
}

export const SummarizePlotsSection: React.FC<SummarizePlotsProps> = ({
  summarizeCalls,
  state,
}) => {
  const [selectedMetrics, setSelectedMetrics] = useState<
    Record<string, boolean> | undefined
  >(undefined);

  // Extract metrics from summarize calls
  const {radarData, allMetricNames} = useMemo(() => {
    const callsByParent: Record<string, any[]> = {};
    // Group calls by parent evaluation
    summarizeCalls.forEach(call => {
      const parentId = call.traceCall?.parent_id || 'unknown';
      if (!callsByParent[parentId]) {
        callsByParent[parentId] = [];
      }
      callsByParent[parentId].push(call);
    });

    const metricNames = new Set<string>();
    const radarData: RadarPlotData = {};

    // Get evaluation IDs in order they appear in state
    const evaluationIds = Object.keys(state.summary.evaluationCalls).reverse();

    // Extract metrics from each evaluation's summarize calls
    evaluationIds.forEach(evalId => {
      const evalCalls = callsByParent[evalId] || [];
      const evalCall = evalCalls[0];

      if (evalCall) {
        const metricsObj = getMetricsFromCall(evalCall);
        if (metricsObj) {
          // Add all metric names to the set
          Object.keys(metricsObj).forEach(key => metricNames.add(key));

          // Add metrics data for this evaluation
          radarData[evalId] = {
            name: state.summary.evaluationCalls[evalId].name || 'model',
            color: state.summary.evaluationCalls[evalId].color,
            metrics: metricsObj,
          };
        }
      }
    });

    return {radarData, allMetricNames: metricNames};
  }, [summarizeCalls, state.summary.evaluationCalls]);

  // Initialize selectedMetrics if null
  useEffect(() => {
    if (selectedMetrics == null) {
      setSelectedMetrics(
        Object.fromEntries(Array.from(allMetricNames).map(m => [m, true]))
      );
    }
  }, [selectedMetrics, allMetricNames]);

  // Filter data based on selected metrics
  const filteredData = useMemo(() => {
    const data: RadarPlotData = {};
    for (const [callId, metricBin] of Object.entries(radarData)) {
      const metrics: {[metric: string]: number} = {};
      for (const [metric, value] of Object.entries(metricBin.metrics)) {
        if (selectedMetrics?.[metric]) {
          metrics[metric] = value;
        }
      }
      if (Object.keys(metrics).length > 0) {
        data[callId] = {
          metrics,
          name: metricBin.name,
          color: metricBin.color,
        };
      }
    }
    return data;
  }, [radarData, selectedMetrics]);

  // Normalize data for radar plot
  const normalizedRadarData = useMemo(() => {
    const data = {...filteredData};
    const metricValues: {[metric: string]: number[]} = {};

    // Collect all values for each metric
    Object.values(data).forEach(callData => {
      Object.entries(callData.metrics).forEach(([metric, value]) => {
        if (!metricValues[metric]) {
          metricValues[metric] = [];
        }
        metricValues[metric].push(value);
      });
    });

    // Normalize each metric
    Object.entries(metricValues).forEach(([metric, values]) => {
      const min = Math.min(...values);
      const max = Math.max(...values);

      if (min !== max) {
        // Handle negative values by shifting
        const shiftedValues = min < 0 ? values.map(v => v - min) : values;
        const maxValue = min < 0 ? max - min : max;

        const maxPower = Math.ceil(Math.log2(maxValue));
        const normalizer = Math.pow(2, maxPower);

        let idx = 0;
        Object.values(data).forEach(callData => {
          if (callData.metrics[metric] !== undefined) {
            const shiftedValue =
              min < 0
                ? callData.metrics[metric] - min
                : callData.metrics[metric];
            callData.metrics[metric] = shiftedValue / normalizer;
            idx++;
          }
        });
      } else {
        // If all values are the same, normalize to 0.5
        Object.values(data).forEach(callData => {
          if (callData.metrics[metric] !== undefined) {
            callData.metrics[metric] = 0.5;
          }
        });
      }
    });

    return data;
  }, [filteredData]);

  // Generate bar plot data
  const barPlotData = useMemo(() => {
    const metrics: {
      [metric: string]: {
        callIds: string[];
        values: number[];
        name: string;
        colors: string[];
      };
    } = {};

    // Reorganize data by metric instead of by call
    for (const [callId, metricBin] of Object.entries(filteredData)) {
      for (const [metric, value] of Object.entries(metricBin.metrics)) {
        if (!metrics[metric]) {
          metrics[metric] = {callIds: [], values: [], name: metric, colors: []};
        }
        metrics[metric].callIds.push(callId);
        metrics[metric].values.push(value);
        metrics[metric].colors.push(metricBin.color);
      }
    }

    // Convert metrics object to Plotly data format
    return Object.entries(metrics).map(([metric, metricBin]) => {
      const maxY = Math.max(...metricBin.values) * 1.1;
      const minY = Math.min(...metricBin.values, 0);
      const plotlyData: Plotly.Data = {
        type: 'bar',
        y: metricBin.values,
        x: metricBin.callIds,
        text: metricBin.values.map(value =>
          Number.isInteger(value) ? value.toString() : value.toFixed(3)
        ),
        textposition: 'outside',
        textfont: {size: 14, color: 'black'},
        name: metric,
        marker: {color: metricBin.colors},
      };
      return {plotlyData, yRange: [minY, maxY] as [number, number]};
    });
  }, [filteredData]);

  // Container dimensions for responsive layout
  const containerRef = useRef<HTMLDivElement>(null);
  const [containerWidth, setContainerWidth] = useState(0);
  const [isInitialRender, setIsInitialRender] = useState(true);
  const [currentPage, setCurrentPage] = useState(0);

  useEffect(() => {
    const updateWidth = () => {
      if (containerRef.current) {
        setContainerWidth(containerRef.current.offsetWidth);
      }
    };

    updateWidth();
    setIsInitialRender(false);

    window.addEventListener('resize', updateWidth);
    return () => window.removeEventListener('resize', updateWidth);
  }, []);

  const plotsPerPage = Math.max(1, Math.floor(containerWidth / PLOT_HEIGHT));

  // Calculate pagination
  const radarPlotWidth = 2;
  const totalBarPlots = barPlotData.length;
  const totalPlotWidth = radarPlotWidth + totalBarPlots;
  const totalPages = Math.ceil(totalPlotWidth / plotsPerPage);

  // Render plots based on current page
  const plotsToShow = useMemo(() => {
    if (isInitialRender) {
      return [];
    }

    // First page always shows radar plot
    if (currentPage === 0) {
      const availableSpace = plotsPerPage - radarPlotWidth;
      return [
        <Box
          key="radar"
          sx={{
            height: PLOT_HEIGHT,
            width: PLOT_HEIGHT * 2,
            borderRadius: BOX_RADIUS,
            border: STANDARD_BORDER,
            padding: PLOT_PADDING,
          }}>
          <PlotlyRadarPlot height={PLOT_HEIGHT} data={normalizedRadarData} />
        </Box>,
        ...barPlotData.slice(0, availableSpace).map((plot, index) => (
          <Box
            key={`bar-${index}`}
            sx={{
              height: PLOT_HEIGHT,
              width: PLOT_HEIGHT,
              borderRadius: BOX_RADIUS,
              border: STANDARD_BORDER,
              paddingTop: PLOT_PADDING - 10,
              paddingBottom: PLOT_PADDING,
              paddingLeft: PLOT_PADDING,
              paddingRight: PLOT_PADDING,
            }}>
            <PlotlyBarPlot
              height={PLOT_HEIGHT}
              plotlyData={plot.plotlyData}
              yRange={plot.yRange}
            />
          </Box>
        )),
      ];
    } else {
      // Subsequent pages show only bar plots
      const startIdx =
        (currentPage - 1) * plotsPerPage + (plotsPerPage - radarPlotWidth);
      const endIdx = startIdx + plotsPerPage;
      return barPlotData.slice(startIdx, endIdx).map((plot, index) => (
        <Box
          key={`bar-${startIdx + index}`}
          sx={{
            height: PLOT_HEIGHT,
            width: PLOT_HEIGHT,
            borderRadius: BOX_RADIUS,
            border: STANDARD_BORDER,
            paddingTop: PLOT_PADDING - 10,
            paddingBottom: PLOT_PADDING,
            paddingLeft: PLOT_PADDING,
            paddingRight: PLOT_PADDING,
          }}>
          <PlotlyBarPlot
            height={PLOT_HEIGHT}
            plotlyData={plot.plotlyData}
            yRange={plot.yRange}
          />
        </Box>
      ));
    }
  }, [
    currentPage,
    plotsPerPage,
    normalizedRadarData,
    barPlotData,
    isInitialRender,
  ]);

  // Pagination details
  const totalPlots = barPlotData.length + 1; // +1 for the radar plot
  const startIndex =
    currentPage === 0 ? 1 : Math.min(plotsPerPage + 1, totalPlots);
  const endIndex =
    currentPage === 0
      ? Math.min(plotsToShow.length, totalPlots)
      : Math.min(startIndex + plotsToShow.length - 1, totalPlots);

  // If no metrics found, show message
  if (allMetricNames.size === 0) {
    return (
      <Alert severity="info">No metric data found in summarize calls.</Alert>
    );
  }

  // Render placeholder during initial render
  if (isInitialRender) {
    return <div ref={containerRef} style={{width: '100%', height: '400px'}} />;
  }

  return (
    <VerticalBox
      sx={{
        paddingLeft: STANDARD_PADDING,
        paddingRight: STANDARD_PADDING,
        flex: '1 1 auto',
        width: '100%',
      }}>
      {/* Header with metrics selector */}
      <HorizontalBox
        sx={{
          width: '100%',
          alignItems: 'center',
          justifyContent: 'flex-start',
        }}>
        <Box
          sx={{
            fontSize: '1.5em',
            fontWeight: 'bold',
          }}>
          Metrics Visualization
        </Box>
        <Box sx={{marginLeft: 'auto'}}>
          <div style={{display: 'flex', alignItems: 'center'}}>
            <div style={{marginRight: '4px'}}>Configure displayed metrics</div>
            <MetricsSelector
              selectedMetrics={selectedMetrics}
              setSelectedMetrics={setSelectedMetrics}
              allMetrics={Array.from(allMetricNames)}
            />
          </div>
        </Box>
      </HorizontalBox>

      {/* Plots container */}
      <div ref={containerRef} style={{width: '100%', display: 'flex'}}>
        <HorizontalBox>{plotsToShow}</HorizontalBox>
      </div>

      {/* Pagination controls */}
      <HorizontalBox sx={{width: '100%'}}>
        <Box
          sx={{
            marginLeft: 'auto',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
          }}>
          <Tailwind>
            <div className="flex items-center">
              <Button
                variant="ghost"
                onClick={() => setCurrentPage(prev => Math.max(prev - 1, 0))}
                disabled={currentPage === 0}
                icon="chevron-next"
                className="rotate-180"
              />
              <span className="mx-2 pb-2 text-sm text-moon-500">
                {startIndex}-{endIndex} of {totalPlots}
              </span>
              <Button
                variant="ghost"
                onClick={() =>
                  setCurrentPage(prev => Math.min(prev + 1, totalPages - 1))
                }
                disabled={currentPage === totalPages - 1}
                icon="chevron-next"
              />
            </div>
          </Tailwind>
        </Box>
      </HorizontalBox>
    </VerticalBox>
  );
};
