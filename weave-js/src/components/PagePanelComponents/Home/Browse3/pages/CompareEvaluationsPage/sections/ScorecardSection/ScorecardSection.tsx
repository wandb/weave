import {Box} from '@material-ui/core';
import React, {useMemo} from 'react';
import styled from 'styled-components';

import {
  MOON_100,
  MOON_600,
} from '../../../../../../../../common/css/color.styles';
import {WeaveObjectRef} from '../../../../../../../../react';
import {Checkbox} from '../../../../../../..';
import {Pill, TagColorName} from '../../../../../../../Tag';
import {NotApplicable} from '../../../../../Browse2/NotApplicable';
import {parseRefMaybe, SmallRef} from '../../../../../Browse2/SmallRef';
import {ValueViewNumber} from '../../../CallPage/ValueViewNumber';
import {
  BOX_RADIUS,
  STANDARD_BORDER,
  STANDARD_PADDING,
} from '../../ecpConstants';
import {SIGNIFICANT_DIGITS} from '../../ecpConstants';
import {getOrderedCallIds, getOrderedModelRefs} from '../../ecpState';
import {EvaluationComparisonState} from '../../ecpTypes';
import {
  adjustValueForDisplay,
  dimensionLabel,
  dimensionUnit,
  resolveDimensionValueForEvaluateCall,
} from '../../ecpUtil';
import {HorizontalBox} from '../../Layout';
import {
  EvaluationCallLink,
  EvaluationModelLink,
} from '../ComparisonDefinitionSection/EvaluationDefinition';

// const FIXED_SCORE_LABEL_WIDTH = 'inherit'; // '150px';

type ScorecardSpecificLegacyScoresType = {
  [scorerId: string]: {
    scorerRef?: string;
    scorerName?: string;
    metrics: {
      [metricKey: string]: {
        displayName: string;
        unit: string;
        lowerIsBetter: boolean;
        modelScores: {[modelRef: string]: number | undefined};
      };
    };
  };
};

const GridCell = styled.div`
  padding: 6px 16px;
  /* white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis; */
  min-width: 100px;
`;

export const ScorecardSection: React.FC<{
  state: EvaluationComparisonState;
}> = props => {
  // console.log(props);
  const baselineRef =
    props.state.data.evaluationCalls[props.state.baselineEvaluationCallId]
      .modelRef;

  const modelRefs = useMemo(
    () => getOrderedModelRefs(props.state),
    [props.state]
  );
  const evalCallIds = useMemo(
    () => getOrderedCallIds(props.state),
    [props.state]
  );

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

  const betterScores: ScorecardSpecificLegacyScoresType = useMemo(() => {
    const res: ScorecardSpecificLegacyScoresType = {};
    Object.entries(props.state.data.evaluationCalls).forEach(
      ([evalCallId, evaluationCall]) => {
        Object.entries(evaluationCall.summaryMetrics).forEach(
          ([metricDimensionId, metricDimension]) => {
            const scorerMetricsDimension =
              props.state.data.scorerMetricDimensions[metricDimensionId];
            const derivedMetricsDimension =
              props.state.data.derivedMetricDimensions[metricDimensionId];
            if (scorerMetricsDimension != null) {
              const scorerRef =
                scorerMetricsDimension.scorerDef.scorerOpOrObjRef;
              const scorerName =
                scorerMetricsDimension.scorerDef.likelyTopLevelKeyName;
              const unit = dimensionUnit(scorerMetricsDimension, true);
              const lowerIsBetter = false;
              if (res[scorerRef] == null) {
                res[scorerRef] = {
                  scorerRef,
                  scorerName,
                  metrics: {},
                };
              }
              if (res[scorerRef].metrics[metricDimensionId] == null) {
                res[scorerRef].metrics[metricDimensionId] = {
                  displayName: dimensionLabel(scorerMetricsDimension),
                  unit,
                  lowerIsBetter,
                  modelScores: {},
                };
              }

              res[scorerRef].metrics[metricDimensionId].modelScores[
                evaluationCall.modelRef
              ] = adjustValueForDisplay(
                resolveDimensionValueForEvaluateCall(
                  scorerMetricsDimension,
                  evaluationCall
                ),
                scorerMetricsDimension.scoreType === 'binary'
              );
            } else if (derivedMetricsDimension != null) {
              const scorerRef = '__DERIVED__';
              const scorerName = '';
              const unit = dimensionUnit(derivedMetricsDimension, true);
              const lowerIsBetter =
                derivedMetricsDimension.shouldMinimize ?? false;
              if (res[scorerRef] == null) {
                res[scorerRef] = {
                  scorerRef,
                  scorerName,
                  metrics: {},
                };
              }
              if (res[scorerRef].metrics[metricDimensionId] == null) {
                res[scorerRef].metrics[metricDimensionId] = {
                  displayName: dimensionLabel(derivedMetricsDimension),
                  unit,
                  lowerIsBetter,
                  modelScores: {},
                };
              }

              res[scorerRef].metrics[metricDimensionId].modelScores[
                evaluationCall.modelRef
              ] = adjustValueForDisplay(
                resolveDimensionValueForEvaluateCall(
                  derivedMetricsDimension,
                  evaluationCall
                ),
                derivedMetricsDimension.scoreType === 'binary'
              );
            } else {
              throw new Error('Unknown metric dimension type');
            }
          }
        );
      }
    );
    // Object.values(props.state.data.evaluationCalls).forEach(evaluationCall => {
    //   Object.keys(evaluationCall.summaryMetrics).forEach(scoreName => {
    //     const scoreRefsParsed = props.state.data.evaluations[
    //       evaluationCall.evaluationRef
    //     ].scorerRefs.map(ref => ({
    //       parsed: parseRef(ref) as WeaveObjectRef,
    //       ref,
    //     }));
    //     const scorerRef = scoreRefsParsed.find(
    //       ref => ref.parsed.artifactName === scoreName
    //     )?.ref;
    //     if (!scorerRef) {
    //       console.error('No score ref found for', scoreName);
    //       return;
    //     }
    //     const parsed = parseRef(scorerRef) as WeaveObjectRef;
    //     if (!res[scoreName]) {
    //       res[scoreName] = {
    //         scorerRef,
    //         scorerName: parsed.artifactName,
    //         metrics: {},
    //       };
    //     }

    //     if (evaluationCall.summaryMetrics[scoreName]) {
    //       Object.keys(evaluationCall.summaryMetrics[scoreName]).forEach(
    //         metricKey => {
    //           const summaryValue = resolveDimensionValueForEvaluateCall(dim, evaluationCall);
    //           evaluationCall.summaryMetrics[scoreName][metricKey];
    //           let value = 0;
    //           let unit = '';
    //           if (isContinuousSummaryScore(summaryValue)) {
    //             value = summaryValue.mean;
    //           } else if (isBinarySummaryScore(summaryValue)) {
    //             value = summaryValue.true_fraction;
    //             unit = '%';
    //           } else {
    //             console.error('Unknown score type', summaryValue);
    //             return;
    //           }
    //           if (!res[scoreName].metrics[metricKey]) {
    //             res[scoreName].metrics[metricKey] = {
    //               displayName: metricKey,
    //               unit,
    //               lowerIsBetter: false,
    //               modelScores: {},
    //             };
    //           }
    //           res[scoreName].metrics[metricKey].modelScores[
    //             evaluationCall.modelRef
    //           ] = value;
    //         }
    //       );
    //     }
    //   });
    // });

    // // Add tokens and latency last
    // Object.values(props.state.data.evaluationCalls).forEach(evaluationCall => {
    //   const scorerKey = '__computed__';
    //   if (!res[scorerKey]) {
    //     res[scorerKey] = {
    //       scorerRef: scorerKey,
    //       scorerName: '',
    //       metrics: {},
    //     };
    //   }

    //   const tokenMetric = 'Total Tokens';
    //   if (!res[scorerKey].metrics[tokenMetric]) {
    //     res[scorerKey].metrics[tokenMetric] = {
    //       displayName: tokenMetric,
    //       unit: '',
    //       lowerIsBetter: true,
    //       modelScores: {},
    //     };
    //   }
    //   res[scorerKey].metrics[tokenMetric].modelScores[evaluationCall.modelRef] =
    //     sum(
    //       Object.values(
    //         evaluationCall._rawEvaluationTraceData.summary.usage ?? {}
    //       ).map(v => v.total_tokens)
    //     );

    //   const meanLatency = 'Avg. Latency';
    //   if (!res[scorerKey].metrics[meanLatency]) {
    //     res[scorerKey].metrics[meanLatency] = {
    //       displayName: meanLatency,
    //       unit: ' ms',
    //       lowerIsBetter: true,
    //       modelScores: {},
    //     };
    //   }
    //   res[scorerKey].metrics[meanLatency].modelScores[evaluationCall.modelRef] =
    //     evaluationCall._rawEvaluationTraceData.output.model_latency.mean ?? 0;
    // });

    return res;
  }, [
    props.state.data.derivedMetricDimensions,
    props.state.data.evaluationCalls,
    props.state.data.scorerMetricDimensions,
  ]);

  // console.log(betterScores);

  let gridTemplateColumns = '';
  gridTemplateColumns += 'min-content '; // Scorer Name
  gridTemplateColumns += 'min-content '; // Metric/Property Name
  gridTemplateColumns += evalCallIds
    .map(() => 'minmax(200px, auto) ')
    .join(' '); // each model

  return (
    <Box
      sx={{
        width: '100%',
        flex: '0 0 auto',
        paddingLeft: STANDARD_PADDING,
        paddingRight: STANDARD_PADDING,
        overflow: 'auto',
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
          Model Comparison
        </Box>
        <div
          style={{
            // fontWeight: 'bold',
            // paddingRight: '10px',
            display: 'flex',
            flexDirection: 'row',
            alignItems: 'flex-end',
            justifyContent: 'flex-end',
            gap: '8px',
            // border: '1px solid #ccc',
            // borderRadius: '6px',
          }}>
          <span>Show all properties</span>
          <Checkbox
            checked={showDifferences}
            onClick={() => setShowDifferences(v => !v)}
          />
        </div>
      </HorizontalBox>
      <div
        style={{
          display: 'grid',
          gridTemplateColumns,
          border: STANDARD_BORDER,
          borderRadius: BOX_RADIUS,
          overflow: 'auto',
          // gap: '16px',
        }}>
        {/* Header Row */}
        <GridCell
          style={{
            fontWeight: 'bold',
            textAlign: 'right',
            gridColumnEnd: 'span 2',
          }}>
          Evaluation
        </GridCell>
        {/* <GridCell></GridCell> */}
        {evalCallIds.map(evalCallId => {
          return (
            <GridCell
              key={evalCallId}
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
        {/* Header Row */}
        <GridCell
          style={{
            fontWeight: 'bold',
            textAlign: 'right',
            gridColumnEnd: 'span 2',
          }}>
          Model
        </GridCell>
        {/* <GridCell></GridCell> */}
        {evalCallIds.map(evalCallId => {
          return (
            <GridCell
              key={evalCallId}
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
        <GridCell
          style={{
            gridColumnEnd: 'span ' + (evalCallIds.length + 2),
            backgroundColor: MOON_100,
            color: MOON_600,
            fontWeight: 'bold',
            borderTop: '1px solid #ccc',
            borderBottom: '1px solid #ccc',
          }}>
          Properties
        </GridCell>

        {/* Model Rows */}
        {Object.entries(modelProps).map(([prop, modelData]) => {
          if (!showDifferences && !propsWithDifferences.includes(prop)) {
            return null;
          }
          return (
            <React.Fragment key={prop}>
              <GridCell
                style={{
                  gridColumnEnd: 'span 2',
                  fontWeight: 'bold',
                  textAlign: 'right',
                  // paddingRight: '10px',
                  // width: FIXED_SCORE_LABEL_WIDTH,
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
                  return (
                    <GridCell key={evalCallId}>
                      <SmallRef objRef={parsed} />
                    </GridCell>
                  );
                } else {
                  return (
                    <GridCell
                      key={evalCallId}
                      style={{
                        lineBreak: 'anywhere',
                        maxHeight: '100px',
                        overflow: 'auto',
                      }}>
                      {modelData[model]}
                    </GridCell>
                  );
                }
              })}
              {/* <GridCell></GridCell> */}
            </React.Fragment>
          );
        })}
        <GridCell
          style={{
            gridColumnEnd: 'span ' + (evalCallIds.length + 2),
            backgroundColor: MOON_100,
            color: MOON_600,
            fontWeight: 'bold',
            borderTop: '1px solid #ccc',
            borderBottom: '1px solid #ccc',
          }}>
          Metrics
        </GridCell>
        {/* Score Rows */}
        {Object.entries(betterScores).map(([key, def]) => {
          // TODO: this might be wrong if the scorers change between evals with the same name!! Need to revisit
          const scorerRefParsed = parseRefMaybe(
            def.scorerRef ?? ''
          ) as WeaveObjectRef | null;
          return (
            <React.Fragment key={key}>
              {def.scorerName && (
                <>
                  <GridCell
                    style={{
                      // vertical span length of metric
                      // gridColumnEnd: 'span ' + (evalCallIds.length + 2),
                      gridColumnEnd: 'span 2',
                      // gridRowEnd: `span ${Object.keys(def.metrics).length}`,
                      borderTop: '1px solid #ccc',
                      fontWeight: 'bold',
                      textAlign: 'left',
                    }}>
                    {scorerRefParsed ? (
                      <SmallRef objRef={scorerRefParsed} />
                    ) : (
                      def.scorerName ?? ''
                    )}
                  </GridCell>
                  <GridCell
                    style={{
                      borderTop: '1px solid #ccc',
                      gridColumnEnd: 'span ' + evalCallIds.length,
                    }}></GridCell>
                </>
              )}
              {Object.keys(def.metrics).map((metricKey, metricNdx) => {
                return (
                  <React.Fragment key={metricKey}>
                    <GridCell
                      style={{
                        gridColumnEnd: 'span 2',
                        // gridColumnEnd: def.scorerName ? 'span 1' : 'span 2',
                        borderBottom:
                          metricNdx === Object.keys(def.metrics).length - 1
                            ? '1px solid #ccc'
                            : '',
                        fontWeight: 'bold',
                        textAlign: 'right',
                        // width: FIXED_SCORE_LABEL_WIDTH,
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
                      // console.log({value});
                      // console.log({baseline, value});
                      let color: TagColorName = 'moon';
                      const diff = (value ?? 0) - (baseline ?? 0);
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
                        : diff.toFixed(SIGNIFICANT_DIGITS);

                      return (
                        <GridCell
                          key={evalCallId}
                          style={{
                            borderBottom:
                              metricNdx === Object.keys(def.metrics).length - 1
                                ? '1px solid #ccc'
                                : '',
                            // borderTop: metricNdx === 0 ? '1px solid #ccc' : '',
                          }}>
                          {value != null ? (
                            <HorizontalBox
                              style={{
                                alignItems: 'center',
                              }}>
                              <span
                                style={{
                                  minWidth: '70px',
                                  // flex: '1 1 auto',
                                }}>
                                <ValueViewNumber
                                  fractionDigits={SIGNIFICANT_DIGITS}
                                  value={value}
                                />
                                {def.metrics[metricKey].unit}
                              </span>
                              {modelRef !== baselineRef &&
                                diff !== 0 &&
                                value != null &&
                                baseline != null && (
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
                        fractionDigits={SIGNIFICANT_DIGITS}
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
