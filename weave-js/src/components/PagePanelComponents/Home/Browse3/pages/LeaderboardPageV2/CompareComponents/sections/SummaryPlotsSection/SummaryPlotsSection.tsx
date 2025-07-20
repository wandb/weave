import {Box} from '@material-ui/core';
import {Button} from '@wandb/weave/components/Button';
import {Tailwind} from '@wandb/weave/components/Tailwind';
import React, {useMemo, useState} from 'react';

import {
  MOON_100,
  MOON_300,
} from '../../../../../../../../../common/css/color.styles';
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
import {filterLatestCallIdsPerModelDataset} from '../../latestEvaluationUtil';
import {MetricsSelector} from './MetricsSelector';
import {PlotlyBarPlot} from './PlotlyBarPlot';
import {PlotlyRadarPlot, RadarPlotData} from './PlotlyRadarPlot';

/**
 * Summary plots produce plots to summarize evaluation comparisons.
 */
export const SummaryPlotsSection: React.FC<{
  state: EvaluationComparisonState;
  setSelectedMetrics: (newModel: Record<string, boolean>) => void;
  initialExpanded?: boolean;
}> = ({state, setSelectedMetrics, initialExpanded = false}) => {
  const [isExpanded, setIsExpanded] = useState(initialExpanded);
  const {allMetricNames} = usePlotDataFromMetrics(state);
  const {selectedMetrics} = state;

  const toggleExpanded = () => {
    setIsExpanded(!isExpanded);
  };

  return (
    <div
      style={{
        backgroundColor: MOON_100,
        width: '100%',
        ...(isExpanded && {paddingBottom: '24px'}),
      }}>
      <Box
        sx={{
          display: 'flex',
          alignItems: 'center',
          borderTop: `1px solid ${MOON_300}`,
          paddingLeft: STANDARD_PADDING,
          paddingRight: STANDARD_PADDING,
          paddingTop: '8px',
          paddingBottom: '8px',
        }}
        style={{
          backgroundColor: 'transparent',
        }}>
        <Tailwind style={{width: '100%'}}>
          <div className="flex w-full items-center gap-8">
            <Button
              variant="ghost"
              icon={isExpanded ? 'chevron-down' : 'chevron-next'}
              size="small"
              onClick={e => {
                e.stopPropagation();
                toggleExpanded();
              }}
            />
            <h3 className="m-0 text-lg">Metrics</h3>
            <div className="ml-auto flex items-center">
              <MetricsSelector
                selectedMetrics={selectedMetrics}
                setSelectedMetrics={setSelectedMetrics}
                allMetrics={Array.from(allMetricNames)}
              />
            </div>
          </div>
        </Tailwind>
      </Box>
      {isExpanded && (
        <Box
          sx={{
            borderTop: 'none',
            borderRadius: '0 0 8px 8px',
          }}>
          <SummaryPlots state={state} setSelectedMetrics={setSelectedMetrics} />
        </Box>
      )}
    </div>
  );
};

export const SummaryPlots: React.FC<{
  state: EvaluationComparisonState;
  setSelectedMetrics: (newModel: Record<string, boolean>) => void;
}> = ({state, setSelectedMetrics}) => {
  const {radarData, allMetricNames} = usePlotDataFromMetrics(state);
  const {selectedMetrics} = state;

  // Don't initialize selectedMetrics here - let the parent component handle it
  // This prevents conflicts with LeaderboardChartsSection's initialization

  const filteredData = useFilteredData(radarData, selectedMetrics);
  const normalizedRadarData = normalizeDataForRadarPlot(filteredData);
  const barPlotData = useBarPlotData(filteredData, state);

  // Filter bar plot data based on selectedMetrics
  const filteredBarPlotData = useMemo(() => {
    if (!selectedMetrics) return barPlotData;

    return barPlotData.filter(plot => {
      const metricToCheck = plot.originalMetric || plot.metric;
      return selectedMetrics[metricToCheck] !== false;
    });
  }, [barPlotData, selectedMetrics]);

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

  const allPlots = useAllPlots(
    normalizedRadarData,
    filteredBarPlotData,
    handleCloseMetric
  );

  return (
    <div style={{width: '100%'}}>
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(300px, 1fr))',
          gap: STANDARD_PADDING,
          paddingLeft: STANDARD_PADDING,
          paddingRight: STANDARD_PADDING,
          width: '100%',
        }}>
        {allPlots}
      </div>
    </div>
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
      bgcolor: 'white',
    }}>
    <PlotlyRadarPlot height={PLOT_HEIGHT} data={data} />
  </Box>
);

const BarPlotBox: React.FC<{
  plot: BarPlotDataItem;
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
      bgcolor: 'white',
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
      onClick={() => onClose(plot.originalMetric || plot.metric)}
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
  barPlotData: BarPlotDataItem[],
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
        // Show metric if selectedMetrics is undefined or if metric is explicitly true
        // Hide only if explicitly false
        if (!selectedMetrics || selectedMetrics[metric] !== false) {
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

// Define the type for bar plot data
type BarPlotDataItem = {
  plotlyData: Plotly.Data;
  yRange: [number, number];
  metric: string;
  originalMetric?: string;
};

const useBarPlotData = (
  filteredData: RadarPlotData,
  state?: EvaluationComparisonState
): BarPlotDataItem[] =>
  useMemo(() => {
    const metrics: {
      [metric: string]: {
        callIds: string[];
        values: number[];
        name: string;
        colors: string[];
        datasets?: string[];
      };
    } = {};

    // Reorganize data by metric instead of by call
    for (const [callId, metricBin] of Object.entries(filteredData)) {
      for (const [metric, value] of Object.entries(metricBin.metrics)) {
        if (!metrics[metric]) {
          metrics[metric] = {
            callIds: [],
            values: [],
            name: metric,
            colors: [],
            datasets: [],
          };
        }
        metrics[metric].callIds.push(callId);
        metrics[metric].values.push(value);
        metrics[metric].colors.push(metricBin.color);

        // Add dataset information if state is available
        if (state) {
          const evalCall = state.summary.evaluationCalls[callId];
          if (evalCall) {
            const evaluation =
              state.summary.evaluations[evalCall.evaluationRef];
            if (evaluation && evaluation.datasetRef) {
              // Extract dataset name from ref
              const datasetMatch = evaluation.datasetRef.match(
                /object\/([^:]+)(?::|$)/
              );
              const datasetName = datasetMatch ? datasetMatch[1] : 'Unknown';
              metrics[metric].datasets!.push(datasetName);
            }
          }
        }
      }
    }

    // Check if we should split by dataset
    const shouldSplitByDataset =
      state &&
      Object.values(metrics).some(m => {
        const uniqueDatasets = new Set(m.datasets || []);
        return uniqueDatasets.size > 1;
      });

    if (shouldSplitByDataset && state) {
      // Group metrics by dataset
      const metricsByDataset: {
        [key: string]: BarPlotDataItem;
      } = {};

      Object.entries(metrics).forEach(([metric, metricBin]) => {
        // Group by dataset
        const datasetGroups: {
          [dataset: string]: {
            callIds: string[];
            values: number[];
            colors: string[];
          };
        } = {};

        metricBin.callIds.forEach((callId, idx) => {
          const dataset = metricBin.datasets![idx] || 'Unknown';
          if (!datasetGroups[dataset]) {
            datasetGroups[dataset] = {callIds: [], values: [], colors: []};
          }
          datasetGroups[dataset].callIds.push(callId);
          datasetGroups[dataset].values.push(metricBin.values[idx]);
          datasetGroups[dataset].colors.push(metricBin.colors[idx]);
        });

        // Create separate plots for each dataset
        Object.entries(datasetGroups).forEach(([dataset, group]) => {
          const maxY = Math.max(...group.values) * 1.1;
          const minY = Math.min(...group.values, 0);
          const plotlyData: Plotly.Data = {
            type: 'bar',
            y: group.values,
            x: group.callIds,
            text: group.values.map(value =>
              Number.isInteger(value) ? value.toString() : value.toFixed(3)
            ),
            textposition: 'outside',
            textfont: {size: 12, color: 'black'},
            name: `${metric} (${dataset})`,
            marker: {color: group.colors},
          };
          const key = `${metric}-${dataset}`;
          metricsByDataset[key] = {
            plotlyData,
            yRange: [minY, maxY] as [number, number],
            metric: key,
            originalMetric: metric,
          };
        });
      });

      return Object.values(metricsByDataset);
    }

    // Original behavior when not splitting by dataset
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
  }, [filteredData, state]);

export const usePlotDataFromMetrics = (
  state: EvaluationComparisonState
): {
  radarData: RadarPlotData;
  allMetricNames: Set<string>;
  datasetSplitInfo?: {[metric: string]: Set<string>};
} => {
  const {hiddenEvaluationIds, filterToLatestEvaluationsPerModel} =
    useCompareEvaluationsState();
  const compositeMetrics = useMemo(() => {
    return buildCompositeMetricsMap(state.summary, 'summary');
  }, [state]);
  const callIds = useMemo(() => {
    const allCallIds = getOrderedCallIds(state).filter(
      id => !hiddenEvaluationIds.has(id)
    );

    // Only apply latest evaluation filtering if we're in leaderboard mode
    if (filterToLatestEvaluationsPerModel) {
      // Filter to keep only the latest evaluation for each model-dataset combination
      return filterLatestCallIdsPerModelDataset(
        allCallIds,
        state.summary.evaluationCalls,
        state.summary.evaluations,
        {},
        true
      );
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

    // Track which metrics have multiple datasets
    const datasetSplitInfo: {[metric: string]: Set<string>} = {};
    metrics.forEach(metric => {
      const datasets = new Set<string>();
      callIds.forEach(callId => {
        const evalCall = state.summary.evaluationCalls[callId];
        if (evalCall) {
          const evaluation = state.summary.evaluations[evalCall.evaluationRef];
          if (evaluation && evaluation.datasetRef) {
            const datasetMatch = evaluation.datasetRef.match(
              /object\/([^:]+)(?::|$)/
            );
            if (datasetMatch) {
              datasets.add(datasetMatch[1]);
            }
          }
        }
      });
      if (datasets.size > 0) {
        datasetSplitInfo[metric.metricLabel] = datasets;
      }
    });

    // Check if we should split by dataset (same logic as bar charts)
    const shouldSplitByDataset = Object.values(datasetSplitInfo).some(
      datasets => datasets.size > 1
    );

    // Build radar data with dataset-aware metric names if needed
    const radarData = Object.fromEntries(
      callIds.map(callId => {
        const evalCall = state.summary.evaluationCalls[callId];
        const evaluation = state.summary.evaluations[evalCall.evaluationRef];
        const datasetName = evaluation?.datasetRef
          ? evaluation.datasetRef.match(/object\/([^:]+)(?::|$)/)?.[1] ||
            'Unknown'
          : 'Unknown';

        return [
          evalCall.callId,
          {
            name: evalCall.name,
            color: evalCall.color,
            metrics: Object.fromEntries(
              metrics.map(metric => {
                // Use dataset-aware metric names if we're splitting by dataset
                const displayMetricName = shouldSplitByDataset
                  ? `${metric.metricLabel} (${datasetName})`
                  : metric.metricLabel;

                return [
                  displayMetricName,
                  metric.evalScores[evalCall.callId] ?? 0,
                ];
              })
            ),
          },
        ];
      })
    );

    // Update allMetricNames to include dataset suffixes when appropriate
    const allMetricNames = new Set<string>();
    if (shouldSplitByDataset) {
      // Add all metric-dataset combinations
      metrics.forEach(metric => {
        const datasets = datasetSplitInfo[metric.metricLabel];
        if (datasets) {
          datasets.forEach(dataset => {
            allMetricNames.add(`${metric.metricLabel} (${dataset})`);
          });
        }
      });
    } else {
      // Add base metric names
      metrics.forEach(metric => {
        allMetricNames.add(metric.metricLabel);
      });
    }

    return {radarData, allMetricNames, datasetSplitInfo};
  }, [
    callIds,
    compositeMetrics,
    state.summary.evaluationCalls,
    state.summary.evaluations,
  ]);
};
