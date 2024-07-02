import {mean} from 'lodash';
import React, {useMemo} from 'react';

import {MOON_500} from '../../../../../../common/css/color.styles';
import {EvaluationComparisonState} from './compareEvaluationsContext';
import {PLOT_HEIGHT, STANDARD_PADDING} from './constants';
import {EvaluationDefinition} from './EvaluationDefinition';
import {HorizontalBox, VerticalBox} from './Layout';
import {PlotlyScatterPlot, ScatterPlotData} from './PlotlyScatterPlot';

export const ScatterFilter: React.FC<{
  state: EvaluationComparisonState;
}> = props => {
  const targetDimension = props.state.comparisonDimension;
  // const primaryDimension: string =
  //   'weave:///shawn/weave-hooman1/op/llm_score:9yF4LQ63Dg1DSWbGX3H6nEqQcFus5hFlWYnZRadF0eA';

  const scorerName = targetDimension.scorerRef;
  // HAXS!
  const scorerKey = targetDimension.scoreKeyPath.split('.').splice(1).join('.');
  // const modelRefs = Object.keys(props.state.data.models);
  const baselineCallId = props.state.baselineEvaluationCallId;
  const baselineModelId =
    props.state.data.evaluationCalls[baselineCallId].modelRef;
  const compareCallId = Object.keys(props.state.data.evaluationCalls).find(
    callId => callId !== baselineCallId
  )!;
  const compareModelId =
    props.state.data.evaluationCalls[compareCallId].modelRef;

  const modelX = baselineModelId;
  const modelY = compareModelId;

  const data = useMemo(() => {
    const series: ScatterPlotData[number] = {
      x: [],
      y: [],
      color: MOON_500,
    };

    if (scorerName === 'model_latency') {
      Object.values(props.state.data.resultRows).forEach(row => {
        const xVals: number[] = [];
        Object.values(row.models[modelX].predictAndScores).forEach(score => {
          const val = score.predictCall?.latencyMs;
          if (typeof val === 'boolean') {
            xVals.push(val ? 1 : 0);
          } else {
            xVals.push(val ?? 0);
          }
        });
        series.x.push(mean(xVals));
        const yVals: number[] = [];
        Object.values(row.models[modelY].predictAndScores).forEach(score => {
          const val = score.predictCall?.latencyMs;
          if (typeof val === 'boolean') {
            yVals.push(val ? 1 : 0);
          } else {
            yVals.push(val ?? 0);
          }
        });
        series.y.push(mean(yVals));
      });
    } else {
      // const [scorerName, scorerKey] = primaryDimension.split('.');
      Object.values(props.state.data.resultRows).forEach(row => {
        const xVals: number[] = [];
        Object.values(row.models[modelX].predictAndScores).forEach(score => {
          const val = score.scores[scorerName].results[scorerKey];
          console.log(val, scorerKey, score.scores[scorerName]);
          if (typeof val === 'boolean') {
            xVals.push(val ? 1 : 0);
          } else {
            xVals.push(val ?? 0);
          }
        });
        series.x.push(mean(xVals));
        const yVals: number[] = [];
        Object.values(row.models[modelY].predictAndScores).forEach(score => {
          const val = score.scores[scorerName].results[scorerKey];
          if (typeof val === 'boolean') {
            yVals.push(val ? 1 : 0);
          } else {
            yVals.push(val ?? 0);
          }
        });
        series.y.push(mean(yVals));
      });
    }
    return [series];
  }, [modelX, modelY, props.state.data.resultRows, scorerKey, scorerName]);
  // console.log(data, props.state);
  const xColor = props.state.data.evaluationCalls[baselineCallId].color;
  const yColor = props.state.data.evaluationCalls[compareCallId].color;

  return (
    <VerticalBox
      sx={{
        width: '100%',
        paddingLeft: STANDARD_PADDING,
        paddingRight: STANDARD_PADDING,
      }}>
      {/* <Alert>Select a region to narrow the data</Alert> */}
      <VerticalBox
        sx={{
          flex: '1 1 auto',
          width: '100%',
          // border: STANDARD_BORDER,
        }}>
        {/* <ScatterDefinition {...props} /> */}
        <HorizontalBox
          sx={{
            justifyContent: 'flex-start',
          }}>
          <EvaluationDefinition state={props.state} callId={compareCallId} />
        </HorizontalBox>
        <PlotlyScatterPlot
          height={PLOT_HEIGHT}
          data={data}
          xColor={xColor}
          yColor={yColor}
        />
        <HorizontalBox
          sx={{
            justifyContent: 'flex-end',
          }}>
          <EvaluationDefinition state={props.state} callId={baselineCallId} />
        </HorizontalBox>
      </VerticalBox>
    </VerticalBox>
  );
};
