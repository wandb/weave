import {Box} from '@material-ui/core';
import {mean} from 'lodash';
import React, {useCallback, useMemo} from 'react';

import {MOON_500} from '../../../../../../common/css/color.styles';
import {useCompareEvaluationsState} from './compareEvaluationsContext';
import {DimensionPicker} from './ComparisonDefinitionHeader';
import {PLOT_HEIGHT, STANDARD_PADDING} from './constants';
import {HorizontalBox, VerticalBox} from './Layout';
import {PlotlyScatterPlot, ScatterPlotData} from './PlotlyScatterPlot';
import {EvaluationComparisonState} from './types';

export const ScatterFilter: React.FC<{
  state: EvaluationComparisonState;
}> = props => {
  const {setRangeSelection} = useCompareEvaluationsState();
  const targetDimension = props.state.comparisonDimension;
  // const primaryDimension: string =
  //   'weave:///shawn/weave-hooman1/op/llm_score:9yF4LQ63Dg1DSWbGX3H6nEqQcFus5hFlWYnZRadF0eA';

  const scorerName = targetDimension.scorerRef;
  // HAXS!
  const scorerKey = targetDimension.scoreKeyPath.split('.').splice(1).join('.');
  // const modelRefs = Object.keys(props.state.data.models);
  const baselineCallId = props.state.baselineEvaluationCallId;
  const compareCallId = Object.keys(props.state.data.evaluationCalls).find(
    callId => callId !== baselineCallId
  )!;

  const data = useMemo(() => {
    const series: ScatterPlotData[number] = {
      x: [],
      y: [],
      color: MOON_500,
    };

    if (scorerName === 'model_latency') {
      Object.values(props.state.data.resultRows).forEach(row => {
        const xVals: number[] = [];
        Object.values(row.evaluations[baselineCallId].predictAndScores).forEach(
          score => {
            const val = score.predictCall?.latencyMs;
            if (typeof val === 'boolean') {
              xVals.push(val ? 1 : 0);
            } else {
              xVals.push(val ?? 0);
            }
          }
        );
        series.x.push(mean(xVals));
        const yVals: number[] = [];
        Object.values(row.evaluations[compareCallId].predictAndScores).forEach(
          score => {
            const val = score.predictCall?.latencyMs;
            if (typeof val === 'boolean') {
              yVals.push(val ? 1 : 0);
            } else {
              yVals.push(val ?? 0);
            }
          }
        );
        series.y.push(mean(yVals));
      });
    } else {
      // const [scorerName, scorerKey] = primaryDimension.split('.');
      Object.values(props.state.data.resultRows).forEach(row => {
        const xVals: number[] = [];
        Object.values(
          row.evaluations[baselineCallId]?.predictAndScores ?? {}
        ).forEach(score => {
          const results = score.scores[scorerName]?.results;
          if (!results) {
            return;
          }
          const val = results[scorerKey];
          // console.log(val, scorerKey, score.scores[scorerName]);
          if (typeof val === 'boolean') {
            xVals.push(val ? 1 : 0);
          } else {
            xVals.push(val ?? 0);
          }
        });
        const yVals: number[] = [];
        Object.values(
          row.evaluations[compareCallId]?.predictAndScores ?? {}
        ).forEach(score => {
          const results = score.scores[scorerName]?.results;
          if (!results) {
            return;
          }
          const val = results[scorerKey];
          if (typeof val === 'boolean') {
            yVals.push(val ? 1 : 0);
          } else {
            yVals.push(val ?? 0);
          }
        });
        if (xVals.length === 0 || yVals.length === 0) {
          return;
        }
        series.x.push(mean(xVals));
        series.y.push(mean(yVals));
      });
    }
    return [series];
  }, [
    baselineCallId,
    compareCallId,
    props.state.data.resultRows,
    scorerKey,
    scorerName,
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
        {/* <DefinitionText text="target metric " /> */}
        <DimensionPicker {...props} />
      </HorizontalBox>
      {/* <Alert>Select a region to narrow the data</Alert> */}
      <VerticalBox
        sx={{
          flex: '1 1 auto',
          width: '100%',
          // border: STANDARD_BORDER,
        }}>
        {/* <ScatterDefinition {...props} /> */}
        {/* <HorizontalBox
          sx={{
            justifyContent: 'flex-start',
          }}>
          <EvaluationDefinition state={props.state} callId={compareCallId} />
        </HorizontalBox> */}
        <PlotlyScatterPlot
          onRangeChange={onRangeChange}
          height={PLOT_HEIGHT}
          data={data}
          xColor={xColor}
          yColor={yColor}
        />
        {/* <HorizontalBox
          sx={{
            justifyContent: 'flex-end',
          }}>
          <EvaluationDefinition state={props.state} callId={baselineCallId} />
        </HorizontalBox> */}
      </VerticalBox>
    </VerticalBox>
  );
};
