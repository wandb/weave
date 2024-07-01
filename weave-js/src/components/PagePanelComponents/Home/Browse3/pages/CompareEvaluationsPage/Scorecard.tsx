import {Box} from '@material-ui/core';
import {sum} from 'lodash';
import React, {useMemo} from 'react';
import styled from 'styled-components';

import {parseRef, WeaveObjectRef} from '../../../../../../react';
import {Checkbox} from '../../../../..';
import {Pill, TagColorName} from '../../../../../Tag';
import {NotApplicable} from '../../../Browse2/NotApplicable';
import {parseRefMaybe, SmallRef} from '../../../Browse2/SmallRef';
import {ValueViewNumber} from '../CallPage/ValueViewNumber';
import {EvaluationComparisonState} from './compareEvaluationsContext';
import {STANDARD_PADDING} from './constants';
import {EvaluationCallLink, EvaluationModelLink} from './EvaluationDefinition';
import {
  isBinarySummaryScore,
  isContinuousSummaryScore,
} from './evaluationResults';
import {HorizontalBox} from './Layout';

const FIXED_SCORE_LABEL_WIDTH = 'inherit'; //'150px';

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

const GridCell = styled.div`
  padding: 8px;
`;

export const ScoreCard: React.FC<{
  state: EvaluationComparisonState;
}> = props => {
  console.log(props);
  const baselineRef =
    props.state.data.evaluationCalls[props.state.baselineEvaluationCallId]
      .modelRef;
  const modelRefs = useMemo(() => {
    const refs = Object.keys(props.state.data.models);
    // Make sure the baseline model is first

    moveItemToFront(refs, baselineRef);
    return refs;
  }, [baselineRef, props.state.data.models]);
  const evalCallIds = useMemo(() => {
    const all = Object.keys(props.state.data.evaluationCalls);
    // Make sure the baseline model is first
    moveItemToFront(all, props.state.baselineEvaluationCallId);
    return all;
  }, [props.state.baselineEvaluationCallId, props.state.data.evaluationCalls]);

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
  gridTemplateColumns += 'min-content '; // Scorer Name
  gridTemplateColumns += 'min-content '; // Metric/Property Name
  gridTemplateColumns += evalCallIds.map(() => 'auto ').join(' '); // each model

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
          gridTemplateColumns,
          // gap: '16px',
        }}>
        {/* Header Row */}
        <GridCell></GridCell>
        <GridCell
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
        </GridCell>
        {evalCallIds.map(evalCallId => {
          const modelRef =
            props.state.data.evaluationCalls[evalCallId].modelRef;
          return (
            <GridCell
              key={modelRef}
              style={{
                fontWeight: 'bold',
                // borderTopLeftRadius: '6px',
                // borderTop: '1px solid #ccc',
                // borderLeft: '1px solid #ccc',
              }}>
              <EvaluationModelLink callId={evalCallId} state={props.state} />
            </GridCell>
          );
        })}
        {/* <GridCell></GridCell> */}
        {/* Model Rows */}
        {Object.entries(modelProps).map(([prop, modelData]) => {
          if (!showDifferences && !propsWithDifferences.includes(prop)) {
            return null;
          }
          return (
            <React.Fragment key={prop}>
              <GridCell></GridCell>
              <GridCell
                style={{
                  fontWeight: 'bold',
                  textAlign: 'right',
                  paddingRight: '10px',
                  width: FIXED_SCORE_LABEL_WIDTH,
                  textOverflow: 'ellipsis',
                }}>
                {prop}
              </GridCell>
              {evalCallIds.map((evalCallId, mNdx) => {
                const model =
                  props.state.data.evaluationCalls[evalCallId].modelRef;
                const parsed = parseRefMaybe(
                  modelProps[prop][model]
                ) as WeaveObjectRef;
                if (parsed) {
                  const parsed = parseRef(
                    modelProps[prop][model]
                  ) as WeaveObjectRef;
                  return (
                    <GridCell key={mNdx}>
                      <SmallRef objRef={parsed} />
                    </GridCell>
                  );
                } else {
                  return <GridCell key={mNdx}>{modelData[model]}</GridCell>;
                }
              })}
              {/* <GridCell></GridCell> */}
            </React.Fragment>
          );
        })}
        {/* Header Row */}
        <GridCell></GridCell>
        <GridCell></GridCell>
        {evalCallIds.map(evalCallId => {
          const modelRef =
            props.state.data.evaluationCalls[evalCallId].modelRef;
          return (
            <GridCell
              key={modelRef}
              style={{
                fontWeight: 'bold',
                // borderTopLeftRadius: '6px',
                // borderTop: '1px solid #ccc',
                // borderLeft: '1px solid #ccc',
              }}>
              <EvaluationCallLink callId={evalCallId} state={props.state} />
            </GridCell>
          );
        })}
        {/* <GridCell></GridCell> */}
        {/* Score Rows */}
        {Object.entries(betterScores).map(([key, def]) => {
          // TODO: this might be wrong if the scorers change between evals with the same name!! Need to revisit
          const scorerRefParsed = parseRefMaybe(
            def.scorerRef ?? ''
          ) as WeaveObjectRef | null;
          return (
            <React.Fragment key={key}>
              <GridCell
                style={{
                  // vertical span length of metric
                  gridRowEnd: `span ${Object.keys(def.metrics).length}`,
                  borderTop: '1px solid #ccc',
                  fontWeight: 'bold',
                  textAlign: 'right',
                }}>
                {scorerRefParsed ? (
                  <SmallRef objRef={scorerRefParsed} />
                ) : (
                  def.scorerName ?? ''
                )}
              </GridCell>
              {Object.keys(def.metrics).map((metricKey, metricNdx) => {
                return (
                  <React.Fragment key={metricKey}>
                    <GridCell
                      style={{
                        borderTop: metricNdx === 0 ? '1px solid #ccc' : '',
                        fontWeight: 'bold',
                        textAlign: 'right',
                        width: FIXED_SCORE_LABEL_WIDTH,
                        textOverflow: 'ellipsis',
                      }}>
                      {def.metrics[metricKey].displayName}
                    </GridCell>
                    {evalCallIds.map((evalCallId, mNdx) => {
                      const modelRef =
                        props.state.data.evaluationCalls[evalCallId].modelRef;
                      // const value = betterScores[key].metrics[metric.key]
                      const baseline =
                        def.metrics[metricKey].modelScores[baselineRef];
                      const value =
                        def.metrics[metricKey].modelScores[modelRef];
                      console.log({value});
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
                        <GridCell
                          key={modelRef}
                          style={{
                            borderTop: metricNdx === 0 ? '1px solid #ccc' : '',
                          }}>
                          {value != null ? (
                            <HorizontalBox
                              style={{
                                alignItems: 'center',
                              }}>
                              <span
                                style={{
                                  minWidth: '100px',
                                }}>
                                <ValueViewNumber
                                  fractionDigits={4}
                                  value={value}
                                />
                                {def.metrics[metricKey].unit}
                              </span>
                              {modelRef !== baselineRef && diff !== 0 && (
                                <Pill
                                  label={
                                    (diff > 0 ? '+' : '') +
                                    diffFixed +
                                    def.metrics[metricKey].unit
                                  }
                                  color={color}
                                />
                              )}
                            </HorizontalBox>
                          ) : (
                            <NotApplicable />
                          )}
                        </GridCell>
                      );
                    })}
                    {/* <GridCell
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
                    </GridCell> */}
                    {/* <GridCell></GridCell> */}
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
