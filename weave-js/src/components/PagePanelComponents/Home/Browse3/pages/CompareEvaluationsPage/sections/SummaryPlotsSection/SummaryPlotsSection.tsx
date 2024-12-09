import {Box} from '@material-ui/core';
import {Button} from '@wandb/weave/components/Button';
import {Tailwind} from '@wandb/weave/components/Tailwind';
import React, {useEffect, useMemo, useRef, useState} from 'react';

import {buildCompositeMetricsMap} from '../../compositeMetricsUtil';
import {
  BOX_RADIUS,
  PLOT_HEIGHT,
  PLOT_PADDING,
  STANDARD_BORDER,
  STANDARD_PADDING,
} from '../../ecpConstants';
import {getOrderedCallIds} from '../../ecpState';
import {EvaluationComparisonState} from '../../ecpState';
import {
  flattenedDimensionPath,
  resolveSummaryMetricValueForEvaluateCall,
} from '../../ecpUtil';
import {HorizontalBox, VerticalBox} from '../../Layout';
import {MetricsSelector} from './MetricsSelector';
import {PlotlyBarPlot} from './PlotlyBarPlot';
import {PlotlyRadarPlot, RadarPlotData} from './PlotlyRadarPlot';

/**
 * Summary plots produce plots to summarize evaluation comparisons.
 */
export const SummaryPlots: React.FC<{
  state: EvaluationComparisonState;
  setSelectedMetrics: (newModel: Record<string, boolean>) => void;
}> = ({state, setSelectedMetrics}) => {
  const {radarData, allMetricNames} = useNormalizedPlotDataFromMetrics(state);
  const {selectedMetrics} = state;

  // Initialize selectedMetrics if null
  useEffect(() => {
    if (selectedMetrics == null) {
      setSelectedMetrics(
        Object.fromEntries(Array.from(allMetricNames).map(m => [m, true]))
      );
    }
  }, [selectedMetrics, setSelectedMetrics, allMetricNames]);

  const filteredData = useFilteredData(radarData, selectedMetrics);
  const normalizedRadarData = normalizeDataForRadarPlot(filteredData);
  const barPlotData = useBarPlotData(filteredData);

  const {
    containerRef,
    isInitialRender,
    plotsPerPage,
    currentPage,
    setCurrentPage,
  } = useContainerDimensions();

  const {plotsToShow, totalPlots, startIndex, endIndex, totalPages} =
    usePaginatedPlots(
      normalizedRadarData,
      barPlotData,
      plotsPerPage,
      currentPage
    );

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
      <SectionHeader
        selectedMetrics={selectedMetrics}
        setSelectedMetrics={setSelectedMetrics}
        allMetrics={Array.from(allMetricNames)}
      />
      <div ref={containerRef} style={{width: '100%', display: 'flex'}}>
        <HorizontalBox>{plotsToShow}</HorizontalBox>
      </div>
      <PaginationControls
        currentPage={currentPage}
        totalPages={totalPages}
        startIndex={startIndex}
        endIndex={endIndex}
        totalPlots={totalPlots}
        onPrevPage={() => setCurrentPage(prev => Math.max(prev - 1, 0))}
        onNextPage={() =>
          setCurrentPage(prev => Math.min(prev + 1, totalPages - 1))
        }
      />
    </VerticalBox>
  );
};

const SectionHeader: React.FC<{
  selectedMetrics: Record<string, boolean> | undefined;
  setSelectedMetrics: (newModel: Record<string, boolean>) => void;
  allMetrics: string[];
}> = ({selectedMetrics, setSelectedMetrics, allMetrics}) => (
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
      Summary Metrics
    </Box>
    <Box sx={{marginLeft: 'auto'}}>
      <div style={{display: 'flex', alignItems: 'center'}}>
        <div style={{marginRight: '4px'}}>Configure displayed metrics</div>
        <MetricsSelector
          selectedMetrics={selectedMetrics}
          setSelectedMetrics={setSelectedMetrics}
          allMetrics={allMetrics}
        />
      </div>
    </Box>
  </HorizontalBox>
);

const RadarPlotBox: React.FC<{data: RadarPlotData}> = ({data}) => (
  <Box
    sx={{
      height: PLOT_HEIGHT,
      width: PLOT_HEIGHT * 2,
      borderRadius: BOX_RADIUS,
      border: STANDARD_BORDER,
      padding: PLOT_PADDING,
    }}>
    <PlotlyRadarPlot height={PLOT_HEIGHT} data={data} />
  </Box>
);

const BarPlotBox: React.FC<{
  plot: {plotlyData: Plotly.Data; yRange: [number, number]};
}> = ({plot}) => (
  <Box
    sx={{
      height: PLOT_HEIGHT,
      width: PLOT_HEIGHT,
      borderRadius: BOX_RADIUS,
      border: STANDARD_BORDER,
      // make a bit more space for the title
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
);

const PaginationControls: React.FC<{
  currentPage: number;
  totalPages: number;
  startIndex: number;
  endIndex: number;
  totalPlots: number;
  onPrevPage: () => void;
  onNextPage: () => void;
}> = ({
  currentPage,
  totalPages,
  startIndex,
  endIndex,
  totalPlots,
  onPrevPage,
  onNextPage,
}) => (
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
            variant="quiet"
            onClick={onPrevPage}
            disabled={currentPage === 0}
            icon="chevron-next"
            className="rotate-180"
          />
          <span className="mx-2 pb-2 text-sm text-moon-500">
            {startIndex}-{endIndex} of {totalPlots}
          </span>
          <Button
            variant="quiet"
            onClick={onNextPage}
            disabled={currentPage === totalPages - 1}
            icon="chevron-next"
          />
        </div>
      </Tailwind>
    </Box>
  </HorizontalBox>
);

const useFilteredData = (
  radarData: RadarPlotData,
  selectedMetrics: Record<string, boolean> | undefined
) =>
  useMemo(() => {
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

function getMetricValuesFromRadarData(radarData: RadarPlotData): {
  [metric: string]: number[];
} {
  const metricValues: {[metric: string]: number[]} = {};
  // Gather all values for each metric
  Object.values(radarData).forEach(callData => {
    Object.entries(callData.metrics).forEach(([metric, value]) => {
      if (!metricValues[metric]) {
        metricValues[metric] = [];
      }
      metricValues[metric].push(value);
    });
  });
  return metricValues;
}

function getMetricMinsFromRadarData(radarData: RadarPlotData): {
  [metric: string]: number;
} {
  const metricValues = getMetricValuesFromRadarData(radarData);
  const metricMins: {[metric: string]: number} = {};
  Object.entries(metricValues).forEach(([metric, values]) => {
    metricMins[metric] = Math.min(...values);
  });
  return metricMins;
}

function normalizeDataForRadarPlot(radarData: RadarPlotData): RadarPlotData {
  const metricMins = getMetricMinsFromRadarData(radarData);

  const normalizedData: RadarPlotData = {};
  Object.entries(radarData).forEach(([callId, callData]) => {
    normalizedData[callId] = {
      name: callData.name,
      color: callData.color,
      metrics: {},
    };

    Object.entries(callData.metrics).forEach(([metric, value]) => {
      const min = metricMins[metric];
      // Only shift values if there are negative values
      const normalizedValue = min < 0 ? value - min : value;
      normalizedData[callId].metrics[metric] = normalizedValue;
    });
  });

  return normalizedData;
}

const useBarPlotData = (filteredData: RadarPlotData) =>
  useMemo(() => {
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
        text: metricBin.values.map(value => value.toFixed(3)),
        textposition: 'outside',
        textfont: {size: 14, color: 'black'},
        name: metric,
        marker: {color: metricBin.colors},
      };
      return {plotlyData, yRange: [minY, maxY] as [number, number]};
    });
  }, [filteredData]);

const useContainerDimensions = () => {
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

  const plotsPerPage = useMemo(() => {
    return Math.max(1, Math.floor(containerWidth / PLOT_HEIGHT));
  }, [containerWidth]);

  return {
    containerRef,
    isInitialRender,
    plotsPerPage,
    currentPage,
    setCurrentPage,
  };
};

const usePaginatedPlots = (
  filteredData: RadarPlotData,
  barPlotData: Array<{plotlyData: Plotly.Data; yRange: [number, number]}>,
  plotsPerPage: number,
  currentPage: number
) => {
  const radarPlotWidth = 2;
  const totalBarPlots = barPlotData.length;
  const totalPlotWidth = radarPlotWidth + totalBarPlots;
  const totalPages = Math.ceil(totalPlotWidth / plotsPerPage);

  const plotsToShow = useMemo(() => {
    // First page always shows radar plot
    if (currentPage === 0) {
      const availableSpace = plotsPerPage - radarPlotWidth;
      return [
        <RadarPlotBox key="radar" data={filteredData} />,
        ...barPlotData
          .slice(0, availableSpace)
          .map((plot, index) => (
            <BarPlotBox key={`bar-${index}`} plot={plot} />
          )),
      ];
    } else {
      // Subsequent pages show only bar plots
      const startIdx =
        (currentPage - 1) * plotsPerPage + (plotsPerPage - radarPlotWidth);
      const endIdx = startIdx + plotsPerPage;
      return barPlotData
        .slice(startIdx, endIdx)
        .map((plot, index) => (
          <BarPlotBox key={`bar-${startIdx + index}`} plot={plot} />
        ));
    }
  }, [currentPage, plotsPerPage, filteredData, barPlotData]);

  // Calculate pagination details
  const totalPlots = barPlotData.length + 1; // +1 for the radar plot
  const startIndex =
    currentPage === 0 ? 1 : Math.min(plotsPerPage + 1, totalPlots);
  const endIndex =
    currentPage === 0
      ? Math.min(plotsToShow.length, totalPlots)
      : Math.min(startIndex + plotsToShow.length - 1, totalPlots);

  return {plotsToShow, totalPlots, startIndex, endIndex, totalPages};
};

function normalizeValues(values: Array<number | undefined>): number[] {
  // find the max value
  // find the power of 2 that is greater than the max value
  // divide all values by that power of 2
  const maxVal = Math.max(...(values.filter(v => v !== undefined) as number[]));
  const maxPower = Math.ceil(Math.log2(maxVal));
  return values.map(val => (val ? val / 2 ** maxPower : 0));
}

const useNormalizedPlotDataFromMetrics = (
  state: EvaluationComparisonState
): {radarData: RadarPlotData; allMetricNames: Set<string>} => {
  const compositeMetrics = useMemo(() => {
    return buildCompositeMetricsMap(state.data, 'summary');
  }, [state]);
  const callIds = useMemo(() => {
    return getOrderedCallIds(state);
  }, [state]);

  return useMemo(() => {
    const normalizedMetrics = Object.values(compositeMetrics)
      .map(scoreGroup => Object.values(scoreGroup.metrics))
      .flat()
      .map(metric => {
        const values = callIds.map(callId => {
          const metricDimension = Object.values(metric.scorerRefs).find(
            scorerRefData => scorerRefData.evalCallIds.includes(callId)
          )?.metric;
          if (!metricDimension) {
            return undefined;
          }
          const val = resolveSummaryMetricValueForEvaluateCall(
            metricDimension,
            state.data.evaluationCalls[callId]
          );
          if (typeof val === 'boolean') {
            return val ? 1 : 0;
          } else {
            return val;
          }
        });
        const normalizedValues = normalizeValues(values);
        const evalScores: {[evalCallId: string]: number | undefined} =
          Object.fromEntries(
            callIds.map((key, i) => [key, normalizedValues[i]])
          );

        const metricLabel = flattenedDimensionPath(
          Object.values(metric.scorerRefs)[0].metric
        );
        return {
          metricLabel,
          evalScores,
        };
      });
    const radarData = Object.fromEntries(
      callIds.map(callId => {
        const evalCall = state.data.evaluationCalls[callId];
        return [
          evalCall.callId,
          {
            name: evalCall.name,
            color: evalCall.color,
            metrics: Object.fromEntries(
              normalizedMetrics.map(metric => {
                return [
                  metric.metricLabel,
                  metric.evalScores[evalCall.callId] ?? 0,
                ];
              })
            ),
          },
        ];
      })
    );
    const allMetricNames = new Set(normalizedMetrics.map(m => m.metricLabel));
    return {radarData, allMetricNames};
  }, [callIds, compositeMetrics, state.data.evaluationCalls]);
};
