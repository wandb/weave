import {Box} from '@material-ui/core';
import {sum} from 'lodash';
import React, {useMemo} from 'react';

import {parseRef, WeaveObjectRef} from '../../../../../../react';
import {ValueViewNumber} from '../CallPage/ValueViewNumber';
import {EvaluationComparisonState} from './compareEvaluationsContext';
import {STANDARD_PADDING} from './constants';
import {
  isBinarySummaryScore,
  isContinuousSummaryScore,
} from './evaluationResults';
import {EvaluationCallLink, EvaluationModelLink} from './EvaluationDefinition';
import {ToggleButton} from '@mui/material';
import {Checkbox, Switch} from '../../../../..';
import {SmallRef} from '../../../Browse2/SmallRef';
import {OpVersionLink} from '../common/Links';
import {HorizontalBox, VerticalBox} from './Layout';
import {Pill, TagColorName} from '../../../../../Tag';

const moveItemToFront = (arr: any[], item: any) => {
  const index = arr.indexOf(item);
  if (index > -1) {
    arr.splice(index, 1);
    arr.unshift(item);
  }
};

type BetterScoresType = {
  [scorerId: string]: {
    scorerRef?: string;
    scorerName?: string;
    metrics: {
      [metricKey: string]: {
        displayName: string;
        unit: string;
        lowerIsBetter: boolean;
        modelScores: {[modelRef: string]: number};
      };
    };
  };
};

export const ScoreCard: React.FC<{
  state: EvaluationComparisonState;
}> = props => {
  const baselineRef =
    props.state.data.evaluationCalls[props.state.baselineEvaluationCallId]
      .modelRef;
  const modelRefs = useMemo(() => {
    const refs = Object.keys(props.state.data.models);
    // Make sure the baseline model is first

    moveItemToFront(refs, baselineRef);
    return refs;
  }, [baselineRef, props.state.data.models]);

  const modelProps = useMemo(() => {
    const propsRes: {[prop: string]: {[ref: string]: any}} = {};
    modelRefs.forEach(ref => {
      const model = props.state.data.models[ref];
      Object.keys(model.properties).forEach(prop => {
        if (!propsRes[prop]) {
          propsRes[prop] = {};
        }
        propsRes[prop][ref] = model.properties[prop];
      });
    });

    // Make sure predict op is last
    modelRefs.forEach(ref => {
      const model = props.state.data.models[ref];
      if (!propsRes.predict) {
        propsRes.predict = {};
      }
      propsRes.predict[ref] = model.predictOpRef;
    });

    return propsRes;
  }, [modelRefs, props.state.data.models]);
  const propsWithDifferences = useMemo(() => {
    return Object.keys(modelProps).filter(prop => {
      const values = Object.values(modelProps[prop]);
      return values.some((value, i) => i > 0 && value !== values[0]);
    });
  }, [modelProps]);
  const [showDifferences, setShowDifferences] = React.useState(false);

  const betterScores: BetterScoresType = useMemo(() => {
    const res: BetterScoresType = {};
    Object.values(props.state.data.evaluationCalls).forEach(evaluationCall => {
      Object.keys(evaluationCall.scores).forEach(scoreName => {
        const scoreRefsParsed = props.state.data.evaluations[
          evaluationCall.evaluationRef
        ].scorerRefs.map(ref => ({
          parsed: parseRef(ref) as WeaveObjectRef,
          ref,
        }));
        const scorerRef = scoreRefsParsed.find(
          ref => ref.parsed.artifactName === scoreName
        )?.ref;
        if (!scorerRef) {
          console.error('No score ref found for', scoreName);
          return;
        }
        const parsed = parseRef(scorerRef) as WeaveObjectRef;
        if (!res[scoreName]) {
          res[scoreName] = {
            scorerRef,
            scorerName: parsed.artifactName,
            metrics: {},
          };
        }

        Object.keys(evaluationCall.scores[scoreName]).forEach(metricKey => {
          const summaryValue = evaluationCall.scores[scoreName][metricKey];
          let value = 0;
          let unit = '';
          if (isContinuousSummaryScore(summaryValue)) {
            value = summaryValue.mean;
          } else if (isBinarySummaryScore(summaryValue)) {
            value = summaryValue.true_fraction;
            unit = '%';
          } else {
            console.error('Unknown score type', summaryValue);
            return;
          }
          if (!res[scoreName].metrics[metricKey]) {
            res[scoreName].metrics[metricKey] = {
              displayName: metricKey,
              unit,
              lowerIsBetter: false,
              modelScores: {},
            };
          }
          res[scoreName].metrics[metricKey].modelScores[
            evaluationCall.modelRef
          ] = value;
        });
      });
    });

    // Add tokens and latency last
    Object.values(props.state.data.evaluationCalls).forEach(evaluationCall => {
      const scorerKey = '__computed__';
      if (!res[scorerKey]) {
        res[scorerKey] = {
          scorerRef: scorerKey,
          scorerName: '',
          metrics: {},
        };
      }

      const tokenMetric = 'Total Tokens';
      if (!res[scorerKey].metrics[tokenMetric]) {
        res[scorerKey].metrics[tokenMetric] = {
          displayName: tokenMetric,
          unit: '',
          lowerIsBetter: true,
          modelScores: {},
        };
      }
      res[scorerKey].metrics[tokenMetric].modelScores[evaluationCall.modelRef] =
        sum(
          Object.values(
            evaluationCall._rawEvaluationTraceData.summary.usage ?? {}
          ).map(v => v.total_tokens)
        );

      const meanLatency = 'Avg. Latency';
      if (!res[scorerKey].metrics[meanLatency]) {
        res[scorerKey].metrics[meanLatency] = {
          displayName: meanLatency,
          unit: ' ms',
          lowerIsBetter: true,
          modelScores: {},
        };
      }
      res[scorerKey].metrics[meanLatency].modelScores[evaluationCall.modelRef] =
        evaluationCall._rawEvaluationTraceData.output.model_latency.mean ?? 0;
    });

    return res;
  }, [props.state.data.evaluationCalls, props.state.data.evaluations]);

  // console.log(betterScores);

  let gridTemplateColumns = '';
  gridTemplateColumns += '1fr '; // Scorer Name
  gridTemplateColumns += '1fr '; // Metric/Property Name
  gridTemplateColumns += modelRefs.map(() => 'auto ').join(' '); // each model

  return (
    <Box
      sx={{
        width: '100%',
        flex: '0 0 auto',
        paddingLeft: STANDARD_PADDING,
        paddingRight: STANDARD_PADDING,
        overflow: 'auto',
      }}>
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: gridTemplateColumns,
          gap: '4px',
        }}>
        {/* Header Row */}
        <div></div>
        <div
          style={{
            fontWeight: 'bold',
            paddingRight: '10px',
            display: 'flex',
            flexDirection: 'row',
            alignItems: 'center',
            justifyContent: 'flex-end',
            gap: '4px',
          }}>
          <span>Show All</span>
          <Checkbox
            checked={showDifferences}
            onClick={() => setShowDifferences(v => !v)}
          />
        </div>
        {modelRefs.map(modelRef => {
          return (
            <div
              key={modelRef}
              style={{
                fontWeight: 'bold',
                // borderTopLeftRadius: '6px',
                // borderTop: '1px solid #ccc',
                // borderLeft: '1px solid #ccc',
              }}>
              <EvaluationModelLink
                callId={
                  Object.entries(props.state.data.evaluationCalls).find(
                    ([_, val]) => val.modelRef === modelRef
                  )![0]
                }
                state={props.state}
              />
            </div>
          );
        })}
        {/* <div></div> */}
        {/* Model Rows */}
        {Object.entries(modelProps).map(([prop, modelData]) => {
          if (!showDifferences && !propsWithDifferences.includes(prop)) {
            return null;
          }
          return (
            <React.Fragment key={prop}>
              <div></div>
              <div
                style={{
                  fontWeight: 'bold',
                  textAlign: 'right',
                  paddingRight: '10px',
                }}>
                {prop}
              </div>
              {modelRefs.map((model, mNdx) => {
                if (prop === 'predict') {
                  const parsed = parseRef(
                    modelProps[prop][model]
                  ) as WeaveObjectRef;
                  return <SmallRef objRef={parsed} />;
                } else {
                  return <div key={mNdx}>{modelData[model]}</div>;
                }
              })}
              {/* <div></div> */}
            </React.Fragment>
          );
        })}
        {/* Header Row */}
        <div></div>
        <div></div>
        {modelRefs.map(modelRef => {
          return (
            <div
              key={modelRef}
              style={{
                fontWeight: 'bold',
                // borderTopLeftRadius: '6px',
                // borderTop: '1px solid #ccc',
                // borderLeft: '1px solid #ccc',
              }}>
              <EvaluationCallLink
                callId={
                  Object.entries(props.state.data.evaluationCalls).find(
                    ([_, val]) => val.modelRef === modelRef
                  )![0]
                }
                state={props.state}
              />
            </div>
          );
        })}
        {/* <div></div> */}
        {/* Score Rows */}
        {Object.entries(betterScores).map(([key, def]) => {
          return (
            <React.Fragment key={key}>
              <div
                style={{
                  // vertical span length of metric
                  gridRowEnd: `span ${Object.keys(def.metrics).length}`,
                  borderTop: '1px solid #ccc',
                  fontWeight: 'bold',
                }}>
                {def.scorerName ?? ''}
              </div>
              {Object.keys(def.metrics).map((metricKey, metricNdx) => {
                return (
                  <React.Fragment key={metricKey}>
                    <div
                      style={{
                        borderTop: metricNdx === 0 ? '1px solid #ccc' : '',
                      }}>
                      {def.metrics[metricKey].displayName}
                    </div>
                    {modelRefs.map((modelRef, mNdx) => {
                      // const value = betterScores[key].metrics[metric.key]
                      const baseline =
                        def.metrics[metricKey].modelScores[baselineRef];
                      const value =
                        def.metrics[metricKey].modelScores[modelRef];
                      // console.log({baseline, value});
                      let color: TagColorName = 'moon';
                      const diff = value - baseline;
                      if (diff > 0) {
                        if (!def.metrics[metricKey].lowerIsBetter) {
                          color = 'green';
                        } else {
                          color = 'red';
                        }
                      } else if (diff < 0) {
                        if (!def.metrics[metricKey].lowerIsBetter) {
                          color = 'red';
                        } else {
                          color = 'green';
                        }
                      } else {
                        color = 'moon';
                      }

                      const diffFixed = Number.isInteger(diff)
                        ? diff.toLocaleString()
                        : diff.toFixed(6);

                      return (
                        <HorizontalBox
                          key={modelRef}
                          style={{
                            borderTop: metricNdx === 0 ? '1px solid #ccc' : '',
                          }}>
                          <div style={{minWidth: '100px'}}>
                            <ValueViewNumber fractionDigits={4} value={value} />
                            {def.metrics[metricKey].unit}
                          </div>
                          {modelRef !== baselineRef && diff !== 0 && (
                            <Pill
                              label={diffFixed + def.metrics[metricKey].unit}
                              color={color}
                            />
                          )}

                          {/* <ValueViewNumber
                                fractionDigits={4}
                                value={value - baseline}
                              />  */}
                        </HorizontalBox>
                      );
                    })}
                    {/* <div
                      style={{
                        borderTop: metricNdx === 0 ? '1px solid #ccc' : '',
                      }}>
                      <ValueViewNumber
                        fractionDigits={4}
                        value={
                          ((scores as any)[metric.key] as any)[modelRefs[0]] -
                          ((scores as any)[metric.key] as any)[modelRefs[1]]
                        }
                      />
                      {metric.unit}
                    </div> */}
                    {/* <div></div> */}
                  </React.Fragment>
                );
              })}
            </React.Fragment>
          );
        })}
      </div>
    </Box>
  );
};
