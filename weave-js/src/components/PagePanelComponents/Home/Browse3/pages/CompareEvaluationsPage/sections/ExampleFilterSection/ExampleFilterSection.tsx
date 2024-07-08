import {Box} from '@material-ui/core';
import {FormControl} from '@material-ui/core';
import {Alert, AlertTitle, Autocomplete, Button} from '@mui/material';
import {mean} from 'lodash';
import React, {useCallback, useMemo} from 'react';

import {MOON_500} from '../../../../../../../../common/css/color.styles';
import {StyledTextField} from '../../../../StyledTextField';
import {useCompareEvaluationsState} from '../../compareEvaluationsContext';
import {PLOT_HEIGHT, STANDARD_PADDING} from '../../ecpConstants';
import {
  EvaluationComparisonState,
  isBinaryScore,
  isContinuousScore,
} from '../../ecpTypes';
import {
  dimensionId,
  dimensionLabel,
  resolveDimensionMetricResultForPASCall,
} from '../../ecpUtil';
import {HorizontalBox, VerticalBox} from '../../Layout';
import {useFilteredAggregateRows} from '../ExampleCompareSection/exampleCompareSectionUtil';
import {PlotlyScatterPlot, ScatterPlotData} from './PlotlyScatterPlot';

const RESULT_FILTER_INSTRUCTIONS =
  'Select a region of point(s) in the plot to filter the examples below.' +
  ' Points on the diagonal are points that have the same value for both evaluations.' +
  ' The X and Y axes represent the values of the selected metric for the baseline and comparison evaluations, respectively.' +
  ' Therefore, points towards the top left of the plot are examples where the comparison evaluation has a higher value than the baseline evaluation; points towards the bottom right are examples where the baseline evaluation has a higher value than the comparison evaluation.';

export const ExampleFilterSection: React.FC<{
  state: EvaluationComparisonState;
}> = props => {
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
      </HorizontalBox>
      <HorizontalBox
        sx={{
          flex: '1 1 auto',
          width: '100%',
          flexWrap: 'wrap',
        }}>
        <SingleDimensionFilter {...props} dimensionIndex={0} />
        <SingleDimensionFilter {...props} dimensionIndex={1} />
      </HorizontalBox>
      <Alert
        severity="info"
        action={
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

const SingleDimensionFilter: React.FC<{
  state: EvaluationComparisonState;
  dimensionIndex: number;
}> = props => {
  const {setComparisonDimensions} = useCompareEvaluationsState();
  const baselineCallId = props.state.baselineEvaluationCallId;
  const compareCallId = Object.keys(props.state.data.evaluationCalls).find(
    callId => callId !== baselineCallId
  )!;

  const targetComparisonDimension =
    props.state.comparisonDimensions?.[props.dimensionIndex]!;
  const targetDimension = targetComparisonDimension.dimension;

  const xIsPercentage = targetDimension?.scoreType === 'binary';
  const yIsPercentage = targetDimension?.scoreType === 'binary';

  const xColor = props.state.data.evaluationCalls[baselineCallId].color;
  const yColor = props.state.data.evaluationCalls[compareCallId].color;

  const {filteredRows} = useFilteredAggregateRows(props.state);
  const filteredDigest = useMemo(() => {
    return new Set(filteredRows.map(row => row.inputDigest));
  }, [filteredRows]);

  const data = useMemo(() => {
    const series: ScatterPlotData = [];
    if (targetDimension != null) {
      Object.entries(props.state.data.resultRows).forEach(([digest, row]) => {
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
          selected: filteredDigest.has(digest),
        });
      });
    }

    return series;
  }, [
    baselineCallId,
    compareCallId,
    filteredDigest,
    props.state.data.resultRows,
    targetDimension,
  ]);

  const onRangeChange = useCallback(
    (xMin?: number, xMax?: number, yMin?: number, yMax?: number) => {
      const res = props.state.comparisonDimensions
        ? [...props.state.comparisonDimensions]
        : [];
      if (xMin == null || xMax == null || yMin == null || yMax == null) {
        res[props.dimensionIndex].rangeSelection = undefined;
      } else {
        res[props.dimensionIndex].rangeSelection = {
          [baselineCallId]: {
            min: xMin,
            max: xMax,
          },
          [compareCallId]: {
            min: yMin,
            max: yMax,
          },
        };
      }
      setComparisonDimensions(res);
    },
    [
      baselineCallId,
      compareCallId,
      props.dimensionIndex,
      props.state.comparisonDimensions,
      setComparisonDimensions,
    ]
  );

  return (
    <VerticalBox
      style={{
        flex: '1 1 ' + PLOT_HEIGHT + 'px',
        width: PLOT_HEIGHT,
      }}>
      <DimensionPicker {...props} dimensionIndex={props.dimensionIndex} />
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
  );
};
const DimensionPicker: React.FC<{
  state: EvaluationComparisonState;
  dimensionIndex: number;
}> = props => {
  const targetComparisonDimension =
    props.state.comparisonDimensions?.[props.dimensionIndex]!;

  const currDimension = targetComparisonDimension.dimension;
  const dimensions = useMemo(() => {
    return [
      ...Object.values(props.state.data.derivedMetricDimensions),
      ...Object.values(props.state.data.scorerMetricDimensions),
    ];
  }, [
    props.state.data.derivedMetricDimensions,
    props.state.data.scorerMetricDimensions,
  ]);
  const {setComparisonDimensions} = useCompareEvaluationsState();

  const dimensionMap = useMemo(() => {
    return Object.fromEntries(dimensions.map(dim => [dimensionId(dim), dim]));
  }, [dimensions]);

  return (
    <FormControl>
      <Autocomplete
        size="small"
        disableClearable
        limitTags={1}
        value={currDimension ? dimensionId(currDimension) : undefined}
        onChange={(event, newValue) => {
          setComparisonDimensions(curr => {
            if (curr == null) {
              return null;
            }
            const res = [...curr];
            res[props.dimensionIndex].dimension = dimensionMap[newValue];
            res[props.dimensionIndex].rangeSelection = undefined;
            return res;
          });
        }}
        getOptionLabel={option => {
          return dimensionLabel(dimensionMap[option]!);
        }}
        options={Object.keys(dimensionMap)}
        renderInput={renderParams => (
          <StyledTextField
            {...renderParams}
            value={currDimension ? dimensionLabel(currDimension) : ''}
            label={'Dimension'}
            sx={{width: '300px'}}
          />
        )}
      />
    </FormControl>
  );
};
