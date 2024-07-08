import {Box, IconButton} from '@material-ui/core';
import {Alert, AlertTitle, Button, Collapse} from '@mui/material';
import {mean} from 'lodash';
import React, {useCallback, useMemo} from 'react';

import {MOON_500} from '../../../../../../../../common/css/color.styles';
import {useCompareEvaluationsState} from '../../compareEvaluationsContext';
import {PLOT_HEIGHT, STANDARD_PADDING} from '../../ecpConstants';
import {
  EvaluationComparisonState,
  isBinaryScore,
  isContinuousScore,
} from '../../ecpTypes';
import {resolveDimensionMetricResultForPASCall} from '../../ecpUtil';
import {HorizontalBox, VerticalBox} from '../../Layout';
import {DimensionPicker} from '../ComparisonDefinitionSection/ComparisonDefinitionSection';
import {PlotlyScatterPlot, ScatterPlotData} from './PlotlyScatterPlot';

const RESULT_FILTER_INSTRUCTIONS =
  'Select a region of point(s) in the plot to filter the examples below.' +
  ' Points on the diagonal are points that have the same value for both evaluations.' +
  ' The X and Y axes represent the values of the selected metric for the baseline and comparison evaluations, respectively.' +
  ' Therefore, points towards the top left of the plot are examples where the comparison evaluation has a higher value than the baseline evaluation; points towards the bottom right are examples where the baseline evaluation has a higher value than the comparison evaluation.';

export const ExampleFilterSection: React.FC<{
  state: EvaluationComparisonState;
}> = props => {
  const {setRangeSelection} = useCompareEvaluationsState();
  const targetDimension = props.state.comparisonDimension;
  const baselineCallId = props.state.baselineEvaluationCallId;
  const compareCallId = Object.keys(props.state.data.evaluationCalls).find(
    callId => callId !== baselineCallId
  )!;

  const xIsPercentage = targetDimension?.scoreType === 'binary';
  const yIsPercentage = targetDimension?.scoreType === 'binary';

  const data = useMemo(() => {
    const series: ScatterPlotData = [];
    // = {
    //   x: [],
    //   y: [],
    //   color: MOON_500,
    // };
    if (targetDimension != null) {
      Object.values(props.state.data.resultRows).forEach(row => {
        const xVals: number[] = [];
        const yVals: number[] = [];
        Object.values(row.evaluations[baselineCallId].predictAndScores).forEach(
          score => {
            const val = resolveDimensionMetricResultForPASCall(
              targetDimension,
              score
            );
            if (val === undefined) {
              return;
            } else if (isBinaryScore(val.value)) {
              xVals.push(val.value ? 1 : 0);
            } else if (isContinuousScore(val.value)) {
              xVals.push(val.value);
            }
          }
        );
        Object.values(row.evaluations[compareCallId].predictAndScores).forEach(
          score => {
            const val = resolveDimensionMetricResultForPASCall(
              targetDimension,
              score
            );
            if (val === undefined) {
              return;
            } else if (isBinaryScore(val.value)) {
              yVals.push(val.value ? 1 : 0);
            } else if (isContinuousScore(val.value)) {
              yVals.push(val.value);
            }
          }
        );
        if (xVals.length === 0 || yVals.length === 0) {
          return;
        }
        series.push({
          x: mean(xVals),
          y: mean(yVals),
          size: 15, // xVals.length,
          color: MOON_500,
        });
      });
    }

    // const minSize = Math.min(...series.map(s => s.size));
    // const maxSize = Math.max(...series.map(s => s.size));
    // const targetRange = [12, 20];
    // series.forEach(s => {
    //   const targetRangeSize = targetRange[1] - targetRange[0];
    //   const sizePct = (1 + (s.size - minSize)) / (1 + (maxSize - minSize));
    //   s.size = targetRange[0] + targetRangeSize * sizePct;
    // });

    return series;
  }, [
    baselineCallId,
    compareCallId,
    props.state.data.resultRows,
    targetDimension,
  ]);
  // console.log(data, props.state);
  const xColor = props.state.data.evaluationCalls[baselineCallId].color;
  const yColor = props.state.data.evaluationCalls[compareCallId].color;

  const onRangeChange = useCallback(
    (xMin?: number, xMax?: number, yMin?: number, yMax?: number) => {
      if (xMin == null || xMax == null || yMin == null || yMax == null) {
        setRangeSelection({});
      } else {
        setRangeSelection({
          [baselineCallId]: {
            min: xMin,
            max: xMax,
          },
          [compareCallId]: {
            min: yMin,
            max: yMax,
          },
        });
      }
    },
    [baselineCallId, compareCallId, setRangeSelection]
  );

  const [isExpanded, setIsExpanded] = React.useState(true);

  return (
    <VerticalBox
      sx={{
        width: '100%',
        paddingLeft: STANDARD_PADDING,
        paddingRight: STANDARD_PADDING,
      }}>
      <HorizontalBox
        sx={{
          width: '100%',
          alignItems: 'center',
          justifyContent: 'flex-start',
          marginBottom: '8px',
        }}>
        <Box
          sx={{
            fontSize: '1.5em',
            fontWeight: 'bold',
          }}>
          Result Filter
        </Box>
        <DimensionPicker {...props} />
      </HorizontalBox>
      <VerticalBox
        sx={{
          flex: '1 1 auto',
          width: '100%',
        }}>
        <PlotlyScatterPlot
          onRangeChange={onRangeChange}
          height={PLOT_HEIGHT}
          data={data}
          xColor={xColor}
          yColor={yColor}
          xIsPercentage={xIsPercentage}
          yIsPercentage={yIsPercentage}
          xTitle={
            'Baseline: ' +
            props.state.data.evaluationCalls[baselineCallId].name +
            ' ' +
            props.state.data.evaluationCalls[baselineCallId].callId.slice(-4)
          }
          yTitle={
            'Challenger: ' +
            props.state.data.evaluationCalls[compareCallId].name +
            ' ' +
            props.state.data.evaluationCalls[compareCallId].callId.slice(-4)
          }
        />
      </VerticalBox>
      <Alert
        severity="info"
        action={
          // Expand icon - j
          <Button
            color="inherit"
            size="small"
            onClick={() => {
              setIsExpanded(!isExpanded);
            }}>
            {isExpanded ? 'COLLAPSE' : 'EXPAND'}
          </Button>
        }
        slotProps={{
          closeIcon: {
            name: '',
          },
        }}>
        <AlertTitle
          sx={{
            marginBottom: isExpanded ? '5px' : '0px',
          }}>
          Plot Details
        </AlertTitle>
        {isExpanded ? RESULT_FILTER_INSTRUCTIONS : ''}
      </Alert>
    </VerticalBox>
  );
};
