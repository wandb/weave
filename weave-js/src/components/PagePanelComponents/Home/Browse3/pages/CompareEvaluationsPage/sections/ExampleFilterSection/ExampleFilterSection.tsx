import {Box} from '@material-ui/core';
import {FormControl} from '@material-ui/core';
import {Alert, AlertTitle, Autocomplete, Button} from '@mui/material';
import _, {mean, sum} from 'lodash';
import React, {useCallback, useMemo} from 'react';

import {MOON_500} from '../../../../../../../../common/css/color.styles';
import {StyledTextField} from '../../../../StyledTextField';
import {useCompareEvaluationsState} from '../../compareEvaluationsContext';
import {
  buildCompositeMetricsMap,
  resolvePeerDimension,
} from '../../compositeMetricsUtil';
import {PLOT_HEIGHT, STANDARD_PADDING} from '../../ecpConstants';
import {MAX_PLOT_DOT_SIZE, MIN_PLOT_DOT_SIZE} from '../../ecpConstants';
import {EvaluationComparisonState} from '../../ecpState';
import {metricDefinitionId} from '../../ecpUtil';
import {
  flattenedDimensionPath,
  resolveScoreMetricResultForPASCall,
} from '../../ecpUtil';
import {HorizontalBox, VerticalBox} from '../../Layout';
import {useFilteredAggregateRows} from '../ExampleCompareSection/exampleCompareSectionUtil';
import {PlotlyScatterPlot, ScatterPlotPoint} from './PlotlyScatterPlot';

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
          Example Filter
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
  const compositeMetricsMap = useMemo(() => {
    return buildCompositeMetricsMap(props.state.data, 'score');
  }, [props.state.data]);

  const {setComparisonDimensions} = useCompareEvaluationsState();
  const baselineCallId = props.state.baselineEvaluationCallId;
  const compareCallId = Object.keys(props.state.data.evaluationCalls).find(
    callId => callId !== baselineCallId
  )!;

  const targetComparisonDimension =
    props.state.comparisonDimensions?.[props.dimensionIndex];

  const targetDimension = targetComparisonDimension
    ? props.state.data.scoreMetrics[targetComparisonDimension.metricId]
    : undefined;

  const xIsPercentage = targetDimension?.scoreType === 'binary';
  const yIsPercentage = targetDimension?.scoreType === 'binary';

  const xColor = props.state.data.evaluationCalls[baselineCallId].color;
  const yColor = props.state.data.evaluationCalls[compareCallId].color;

  const {filteredRows} = useFilteredAggregateRows(props.state);
  const filteredDigest = useMemo(() => {
    return new Set(filteredRows.map(row => row.inputDigest));
  }, [filteredRows]);

  const data = useMemo(() => {
    const series: Array<ScatterPlotPoint & {count: number}> = [];
    if (targetDimension != null) {
      const baselineTargetDimension = resolvePeerDimension(
        compositeMetricsMap,
        baselineCallId,
        targetDimension
      );
      const compareTargetDimension = resolvePeerDimension(
        compositeMetricsMap,
        compareCallId,
        targetDimension
      );

      if (baselineTargetDimension != null && compareTargetDimension != null) {
        Object.entries(props.state.data.resultRows).forEach(([digest, row]) => {
          const xVals: number[] = [];
          const yVals: number[] = [];
          Object.values(
            row.evaluations[baselineCallId]?.predictAndScores ?? {}
          ).forEach(score => {
            const val = resolveScoreMetricResultForPASCall(
              baselineTargetDimension,
              score
            );
            if (val == null) {
              return;
            } else if (isBinaryScore(val.value)) {
              xVals.push(val.value ? 1 : 0);
            } else if (isContinuousScore(val.value)) {
              xVals.push(val.value);
            }
          });
          Object.values(
            row.evaluations[compareCallId]?.predictAndScores ?? {}
          ).forEach(score => {
            const val = resolveScoreMetricResultForPASCall(
              compareTargetDimension,
              score
            );
            if (val == null) {
              return;
            } else if (isBinaryScore(val.value)) {
              yVals.push(val.value ? 1 : 0);
            } else if (isContinuousScore(val.value)) {
              yVals.push(val.value);
            }
          });
          if (xVals.length === 0 || yVals.length === 0) {
            return;
          }
          series.push({
            x: mean(xVals),
            y: mean(yVals),
            count: xVals.length,
            size: MIN_PLOT_DOT_SIZE,
            color: MOON_500,
            selected: filteredDigest.has(digest),
          });
        });

        if (targetDimension.scoreType === 'binary') {
          // Here we are going to further group the points by their x and y values
          // since the points are going to be discrete, and stacked. Note, while it
          // is true that each individual trial is either a 0 or 1, the mean of the
          // trials can be a float.
          const grouped = _.groupBy(series, point => `${point.x}-${point.y}`);
          const counts = Object.values(grouped).map(points =>
            sum(points.map(point => point.count))
          );
          const minCount = Math.min(...counts);
          const maxCount = Math.max(...counts);

          const sizeForCount = (count: number) => {
            if (minCount === maxCount) {
              return MIN_PLOT_DOT_SIZE;
            }
            return (
              MIN_PLOT_DOT_SIZE +
              ((count - minCount) / (maxCount - minCount)) *
                (MAX_PLOT_DOT_SIZE - MIN_PLOT_DOT_SIZE)
            );
          };
          return Object.values(grouped).map(points => {
            const count = sum(points.map(point => point.count));
            return {
              x: points[0].x, // x is the same for all points in the group
              y: points[0].y, // y is the same for all points in the group
              size: sizeForCount(count),
              count,
              color: points[0].color,
              selected: points.some(point => point.selected),
            };
          });
        }
      }
    }

    return series;
  }, [
    baselineCallId,
    compareCallId,
    compositeMetricsMap,
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
    props.state.comparisonDimensions?.[props.dimensionIndex];

  const currDimension = targetComparisonDimension
    ? props.state.data.scoreMetrics[targetComparisonDimension.metricId]
    : undefined;
  const {setComparisonDimensions} = useCompareEvaluationsState();

  const dimensionMap = props.state.data.scoreMetrics;

  return (
    <FormControl
      style={{
        paddingTop: '6px',
      }}>
      <Autocomplete
        size="small"
        disableClearable
        limitTags={1}
        value={currDimension ? metricDefinitionId(currDimension) : undefined}
        onChange={(event, newValue) => {
          const res = props.state.comparisonDimensions
            ? [...props.state.comparisonDimensions]
            : [];
          res[props.dimensionIndex].metricId = metricDefinitionId(
            dimensionMap[newValue]
          );
          res[props.dimensionIndex].rangeSelection = undefined;
          setComparisonDimensions(res);
        }}
        getOptionLabel={option => {
          return flattenedDimensionPath(dimensionMap[option]!);
        }}
        options={Object.keys(dimensionMap)}
        renderInput={renderParams => (
          <StyledTextField
            {...renderParams}
            value={currDimension ? flattenedDimensionPath(currDimension) : ''}
            label={'Dimension'}
            sx={{width: '300px'}}
          />
        )}
      />
    </FormControl>
  );
};

const isBinaryScore = (score: any): score is boolean => {
  return typeof score === 'boolean';
};
const isContinuousScore = (score: any): score is number => {
  return typeof score === 'number';
};
