import {Box} from '@material-ui/core';
import React, {useMemo} from 'react';

import {
  BOX_RADIUS,
  PLOT_HEIGHT,
  PLOT_PADDING,
  STANDARD_BORDER,
  STANDARD_PADDING,
} from '../../ecpConstants';
import {getOrderedCallIds} from '../../ecpState';
import {EvaluationComparisonState} from '../../ecpTypes';
import {
  dimensionLabel,
  dimensionShouldMinimize,
  dimensionUnit,
  resolveDimensionValueForEvaluateCall,
} from '../../ecpUtil';
import {HorizontalBox, VerticalBox} from '../../Layout';
import {PlotlyBarPlot} from './PlotlyBarPlot';
import {PlotlyRadarPlot, RadarPlotData} from './PlotlyRadarPlot';

/**
 * Summary plots produce plots to summarize evaluation comparisons.
 */
export const SummaryPlots: React.FC<{
  state: EvaluationComparisonState;
}> = props => {
  const plotlyRadarData = useNormalizedPlotDataFromMetrics(props.state);

  return (
    <VerticalBox
      sx={{
        paddingLeft: STANDARD_PADDING,
        paddingRight: STANDARD_PADDING,
        flex: '1 1 auto',
        width: '100%',
      }}>
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
      </HorizontalBox>
      <HorizontalBox
        sx={{
          flexWrap: 'wrap',
        }}>
        <Box
          sx={{
            flex: '1 2 ' + PLOT_HEIGHT + 'px',
            height: PLOT_HEIGHT,
            borderRadius: BOX_RADIUS,
            border: STANDARD_BORDER,
            overflow: 'hidden',
            alignContent: 'center',
            width: PLOT_HEIGHT,
          }}>
          <PlotlyRadarPlot height={PLOT_HEIGHT} data={plotlyRadarData} />
        </Box>
        <Box
          sx={{
            flex: '2 1 ' + PLOT_HEIGHT + 'px',
            height: PLOT_HEIGHT,
            overflow: 'hidden',
            borderRadius: BOX_RADIUS,
            border: STANDARD_BORDER,
            padding: PLOT_PADDING,
            width: PLOT_HEIGHT,
          }}>
          <PlotlyBarPlot height={PLOT_HEIGHT} data={plotlyRadarData} />
        </Box>
      </HorizontalBox>
    </VerticalBox>
  );
};
const normalizeValues = (values: Array<number | undefined>): number[] => {
  // find the max value
  // find the power of 2 that is greater than the max value
  // divide all values by that power of 2
  const maxVal = Math.max(...(values.filter(v => v !== undefined) as number[]));
  const maxPower = Math.ceil(Math.log2(maxVal));
  return values.map(val => (val ? val / 2 ** maxPower : 0));
};
const useNormalizedPlotDataFromMetrics = (
  state: EvaluationComparisonState
): RadarPlotData => {
  const metrics = useMemo(() => {
    return summaryMetrics(state);
  }, [state]);
  const callIds = useMemo(() => {
    return getOrderedCallIds(state);
  }, [state]);

  return useMemo(() => {
    const normalizedMetrics = metrics.map(metric => {
      const keys = Object.keys(metric.values);
      const values = keys.map(key => metric.values[key]);
      const normalizedValues = normalizeValues(values);

      return {
        ...metric,
        values: Object.fromEntries(
          keys.map((key, i) => [key, normalizedValues[i]])
        ),
      };
    });
    return Object.fromEntries(
      callIds.map(callId => {
        const evalCall = state.data.evaluationCalls[callId];
        return [
          evalCall.callId,
          {
            name: evalCall.name,
            color: evalCall.color,
            metrics: Object.fromEntries(
              normalizedMetrics.map(metric => {
                return [metric.path, metric.values[evalCall.callId]];
              })
            ),
          },
        ];
      })
    );
  }, [callIds, metrics, state.data.evaluationCalls]);
};

type SimplifiedSummaryMetric = {
  path: string;
  unit: string;
  lowerIsBetter: boolean;
  values: {[callId: string]: number | undefined};
};

const summaryMetrics = (
  state: EvaluationComparisonState
): SimplifiedSummaryMetric[] => {
  const results: SimplifiedSummaryMetric[] = [];
  const allEntries = [
    ...Object.entries(state.data.scorerMetricDimensions),
    ...Object.entries(state.data.derivedMetricDimensions),
  ];
  allEntries.forEach(([metricId, metric]) => {
    results.push({
      path: dimensionLabel(metric),
      unit: dimensionUnit(metric),
      lowerIsBetter: dimensionShouldMinimize(metric),
      values: Object.fromEntries(
        Object.entries(state.data.evaluationCalls).map(([callId, call]) => [
          callId,
          resolveDimensionValueForEvaluateCall(metric, call),
        ])
      ),
    });
  });

  return results;
};
