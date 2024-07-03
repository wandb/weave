import {Box} from '@material-ui/core';
import React, {useMemo} from 'react';

import {
  BOX_RADIUS,
  PLOT_HEIGHT,
  PLOT_PADDING,
  STANDARD_BORDER,
  STANDARD_PADDING,
} from './constants';
import {evaluationMetrics} from './evaluations';
import {HorizontalBox, VerticalBox} from './Layout';
import {PlotlyBarPlot} from './PlotlyBarPlot';
import {PlotlyRadarPlot, RadarPlotData} from './PlotlyRadarPlot';
import {EvaluationComparisonState} from './types';
import {getOrderedCallIds} from './evaluationResults';

export const SummaryPlots: React.FC<{
  state: EvaluationComparisonState;
}> = props => {
  const plotlyRadarData = useNormalizedRadarPlotDataFromMetrics(props.state);

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
      <HorizontalBox>
        <Box
          sx={{
            flex: '1 0 auto',
            height: PLOT_HEIGHT,
            // width: PLOT_HEIGHT * 2,
            borderRadius: BOX_RADIUS,
            border: STANDARD_BORDER,
            overflow: 'hidden',
            alignContent: 'center',
          }}>
          <PlotlyRadarPlot height={PLOT_HEIGHT} data={plotlyRadarData} />
          {/* <PlotlyRadarPlot /> */}
          {/* // <PlotlyRadialPlot /> */}
        </Box>
        <Box
          sx={{
            flex: '1 1 auto',
            height: PLOT_HEIGHT,
            width: '100%',
            overflow: 'hidden',
            borderRadius: BOX_RADIUS,
            border: STANDARD_BORDER,
            padding: PLOT_PADDING,
          }}>
          <PlotlyBarPlot height={PLOT_HEIGHT} data={plotlyRadarData} />
        </Box>
      </HorizontalBox>
      {/* <RadarPlot plotlyRadarData={plotlyRadarData} />
            <BarPlots plotlyRadarData={plotlyRadarData}} /> */}
    </VerticalBox>
  );
};
const normalizeValues = (values: number[]): number[] => {
  // find the max value
  // find the power of 2 that is greater than the max value
  // divide all values by that power of 2
  const maxVal = Math.max(...values);
  const maxPower = Math.ceil(Math.log2(maxVal));
  return values.map(val => val / 2 ** maxPower);
};
const useNormalizedRadarPlotDataFromMetrics = (
  state: EvaluationComparisonState
): RadarPlotData => {
  const metrics = useMemo(() => {
    return evaluationMetrics(state);
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
  }, [metrics, state.data.evaluationCalls]);
};
