import {Box} from '@material-ui/core';
import {Button} from '@wandb/weave/components/Button';
import React, {useEffect, useMemo} from 'react';

import {useCompareEvaluationsState} from '../../compareEvaluationsContext';
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
import {filterLatestCallIdsPerModel} from '../../latestEvaluationUtil';
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
  const {radarData, allMetricNames} = usePlotDataFromMetrics(state);
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

  const handleCloseMetric = React.useCallback(
    (metric: string) => {
      if (selectedMetrics) {
        setSelectedMetrics({
          ...selectedMetrics,
          [metric]: false,
        });
      }
    },
    [setSelectedMetrics, selectedMetrics]
  );

  const allPlots = useAllPlots(normalizedRadarData, barPlotData, handleCloseMetric);

  return (
    <VerticalBox
      sx={{
        width: '100%',
        gridGap: STANDARD_PADDING / 2,
      }}>
      <HorizontalBox
        sx={{
          alignItems: 'center',
          justifyContent: 'flex-start',
        }}>
        <MetricsSelector
          selectedMetrics={selectedMetrics}
          setSelectedMetrics={setSelectedMetrics}
          allMetrics={Array.from(allMetricNames)}
        />
      </HorizontalBox>

      <div style={{width: '100%'}}>
        <div
          style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fit, minmax(300px, 1fr))',
            gap: STANDARD_PADDING,
            width: '100%',
          }}>
          {allPlots}
        </div>
      </div>
    </VerticalBox>
  );
};

const RadarPlotBox: React.FC<{data: RadarPlotData}> = ({data}) => (
  <Box
    sx={{
      height: PLOT_HEIGHT,
      borderRadius: BOX_RADIUS,
      border: STANDARD_BORDER,
      padding: PLOT_PADDING,
      width: '100%',
      minWidth: '300px',
    }}>
    <PlotlyRadarPlot height={PLOT_HEIGHT} data={data} />
  </Box>
);

const BarPlotBox: React.FC<{
  plot: {plotlyData: Plotly.Data; yRange: [number, number]; metric: string};
  onClose: (metric: string) => void;
}> = ({plot, onClose}) => (
  <Box
    sx={{
      position: 'relative',
      height: PLOT_HEIGHT,
      borderRadius: BOX_RADIUS,
      border: STANDARD_BORDER,
      paddingTop: PLOT_PADDING - 30,
      paddingBottom: PLOT_PADDING,
      paddingLeft: PLOT_PADDING,
      paddingRight: PLOT_PADDING,
      width: '100%',
      minWidth: '300px',
    }}>
    <Button
      variant="ghost"
      size="small"
      style={{
        position: 'absolute',
        top: 4,
        right: 4,
        minWidth: 0,
        width: 24,
        height: 24,
        padding: 0,
        zIndex: 1,
      }}
      onClick={() => onClose(plot.metric)}
      icon="close"
      aria-label={`Hide ${plot.metric}`}
    />
    <PlotlyBarPlot
      height={PLOT_HEIGHT}
      plotlyData={plot.plotlyData}
      yRange={plot.yRange}
    />
  </Box>
);

const useAllPlots = (
  filteredData: RadarPlotData,
  barPlotData: Array<{
    plotlyData: Plotly.Data;
    yRange: [number, number];
    metric: string;
  }>,
  onClose: (metric: string) => void
) => {
  return useMemo(() => {
    const plots = [];

    // Always show radar plot first if we have data
    if (Object.keys(filteredData).length > 0) {
      plots.push(<RadarPlotBox key="radar" data={filteredData} />);
    }

    // Add all bar plots
    barPlotData.forEach((plot, index) => {
      plots.push(
        <BarPlotBox key={`bar-${index}`} plot={plot} onClose={onClose} />
      );
    });

    return plots;
  }, [filteredData, barPlotData, onClose]);
};

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

function getMetricValuesMap(radarData: RadarPlotData): {
  [metric: string]: number[];
} {
  const metricValues: {[metric: string]: number[]} = {};
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

function normalizeMetricValues(values: number[]): {
  normalizedValues: number[];
  normalizer: number;
} {
  const min = Math.min(...values);
  const max = Math.max(...values);

  if (min === max) {
    return {
      normalizedValues: values.map(() => 0.5),
      normalizer: 1,
    };
  }

  // Handle negative values by shifting
  const shiftedValues = min < 0 ? values.map(v => v - min) : values;
  const maxValue = min < 0 ? max - min : max;

  const maxPower = Math.ceil(Math.log2(maxValue));
  const normalizer = Math.pow(2, maxPower);

  return {
    normalizedValues: shiftedValues.map(v => v / normalizer),
    normalizer,
  };
}

function normalizeDataForRadarPlot(
  radarDataOriginal: RadarPlotData
): RadarPlotData {
  const radarData = Object.fromEntries(
    Object.entries(radarDataOriginal).map(([callId, callData]) => [
      callId,
      {...callData, metrics: {...callData.metrics}},
    ])
  );

  const metricValues = getMetricValuesMap(radarData);

  // Normalize each metric independently
  Object.entries(metricValues).forEach(([metric, values]) => {
    const {normalizedValues} = normalizeMetricValues(values);
    Object.values(radarData).forEach((callData, index) => {
      callData.metrics[metric] = normalizedValues[index];
    });
  });

  return radarData;
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
        text: metricBin.values.map(value =>
          Number.isInteger(value) ? value.toString() : value.toFixed(3)
        ),
        textposition: 'outside',
        textfont: {size: 12, color: 'black'},
        name: metric,
        marker: {color: metricBin.colors},
      };
      return {plotlyData, yRange: [minY, maxY] as [number, number], metric};
    });
  }, [filteredData]);


const usePlotDataFromMetrics = (
  state: EvaluationComparisonState
): {radarData: RadarPlotData; allMetricNames: Set<string>} => {
  const {hiddenEvaluationIds, filterToLatestEvaluationsPerModel} = useCompareEvaluationsState();
  const compositeMetrics = useMemo(() => {
    return buildCompositeMetricsMap(state.summary, 'summary');
  }, [state]);
  const callIds = useMemo(() => {
    const allCallIds = getOrderedCallIds(state).filter(id => !hiddenEvaluationIds.has(id));
    
    // Only apply latest evaluation filtering if we're in leaderboard mode
    if (filterToLatestEvaluationsPerModel) {
      // Filter to keep only the latest evaluation for each model
      return filterLatestCallIdsPerModel(allCallIds, state.summary.evaluationCalls, {}, true);
    }
    
    return allCallIds;
  }, [state, hiddenEvaluationIds, filterToLatestEvaluationsPerModel]);

  return useMemo(() => {
    const metrics = Object.values(compositeMetrics)
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
            state.summary.evaluationCalls[callId]
          );
          if (typeof val === 'boolean') {
            return val ? 1 : 0;
          } else {
            return val;
          }
        });
        const evalScores: {[evalCallId: string]: number | undefined} =
          Object.fromEntries(callIds.map((key, i) => [key, values[i]]));

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
        const evalCall = state.summary.evaluationCalls[callId];
        return [
          evalCall.callId,
          {
            name: evalCall.name,
            color: evalCall.color,
            metrics: Object.fromEntries(
              metrics.map(metric => {
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
    const allMetricNames = new Set(metrics.map(m => m.metricLabel));
    return {radarData, allMetricNames};
  }, [callIds, compositeMetrics, state.summary.evaluationCalls]);
};
