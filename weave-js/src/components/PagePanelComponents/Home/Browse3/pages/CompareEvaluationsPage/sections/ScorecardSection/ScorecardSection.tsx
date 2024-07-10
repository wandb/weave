/**
 * TODO:
 * * Summary metrics: Currently just shows the baseline
 *    * Use this new format from `ScorecardSpecificLegacyScoresType`. Perhaps this is a good chance to align on the format
 * * Example Filters: Currently shows all scorers
 *    * Use this new format from `ScorecardSpecificLegacyScoresType`. Perhaps this is a good chance to align on the format
 * * Output Comparison: Currently shows all scorers
 *    * When 1 scorer, show the ref
 *    * When >1 scorer, sho warning icon with hover info (probably use the same component as scorecard)
 */

import {Box, Tooltip} from '@material-ui/core';
import {Alert} from '@mui/material';
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

const VARIATION_WARNING_TITLE = 'Variation detected';
const VARIATION_WARNING_EXPLAINATION =
  'The scoring function logic varies between evaluations. Take precaution when comparing results.';

type ScorecardSpecificLegacyScoresType = {
  [scorerGroupName: string]: {
    evalCallIdToScorerRef: {[evalCallId: string]: string}; // multiple means we might not have apples to apples comparison
    scorerName?: string;
    metrics: {
      [metricName: string]: {
        scorerRefToMetricKey: {[scorerRef: string]: string};
        displayName: string;
        unit: string;
        lowerIsBetter: boolean;
        evalScores: {[evalCallId: string]: number | undefined};
      };
    };
  };
};

const GridCell = styled.div`
  padding: 6px 16px;
  min-width: 100px;
`;

export const ScorecardSection: React.FC<{
  state: EvaluationComparisonState;
}> = props => {
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
  const [diffOnly, setDiffOnly] = React.useState(true);

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
              if (res[scorerName] == null) {
                res[scorerName] = {
                  evalCallIdToScorerRef: {},
                  scorerName,
                  metrics: {},
                };
              }
              res[scorerName].evalCallIdToScorerRef[evalCallId] = scorerRef;

              const displayName = dimensionLabel(scorerMetricsDimension);
              if (res[scorerName].metrics[displayName] == null) {
                res[scorerName].metrics[displayName] = {
                  displayName,
                  scorerRefToMetricKey: {[scorerRef]: metricDimensionId},
                  unit,
                  lowerIsBetter,
                  evalScores: {},
                };
              }
              if (
                res[scorerName].metrics[displayName].scorerRefToMetricKey[
                  scorerRef
                ] == null
              ) {
                res[scorerName].metrics[displayName].scorerRefToMetricKey[
                  scorerRef
                ] = metricDimensionId;
              }

              res[scorerName].metrics[displayName].evalScores[
                evaluationCall.callId
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
              if (res[scorerName] == null) {
                res[scorerName] = {
                  evalCallIdToScorerRef: {},
                  scorerName,
                  metrics: {},
                };
              }
              res[scorerName].evalCallIdToScorerRef[evalCallId] = scorerRef;

              const displayName = dimensionLabel(derivedMetricsDimension);
              if (res[scorerName].metrics[displayName] == null) {
                res[scorerName].metrics[displayName] = {
                  displayName,
                  scorerRefToMetricKey: {[scorerRef]: metricDimensionId},
                  unit,
                  lowerIsBetter,
                  evalScores: {},
                };
              }
              if (
                res[scorerName].metrics[displayName].scorerRefToMetricKey[
                  scorerRef
                ] == null
              ) {
                res[scorerName].metrics[displayName].scorerRefToMetricKey[
                  scorerRef
                ] = metricDimensionId;
              }

              res[scorerName].metrics[displayName].evalScores[
                evaluationCall.callId
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
    return res;
  }, [
    props.state.data.derivedMetricDimensions,
    props.state.data.evaluationCalls,
    props.state.data.scorerMetricDimensions,
  ]);

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
          Scorecard
        </Box>
      </HorizontalBox>
      <div
        style={{
          display: 'grid',
          gridTemplateColumns,
          border: STANDARD_BORDER,
          borderRadius: BOX_RADIUS,
          overflow: 'auto',
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
        {evalCallIds.map(evalCallId => {
          return (
            <GridCell
              key={evalCallId}
              style={{
                fontWeight: 'bold',
              }}>
              <EvaluationCallLink callId={evalCallId} state={props.state} />
            </GridCell>
          );
        })}
        <GridCell
          style={{
            fontWeight: 'bold',
            textAlign: 'right',
            gridColumnEnd: 'span 2',
          }}>
          Model
        </GridCell>
        {evalCallIds.map(evalCallId => {
          return (
            <GridCell
              key={evalCallId}
              style={{
                fontWeight: 'bold',
              }}>
              <EvaluationModelLink callId={evalCallId} state={props.state} />
            </GridCell>
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
            display: 'flex',
            flexDirection: 'row',
            justifyContent: 'space-between',
            alignItems: 'center',
          }}>
          Properties
          <div
            style={{
              display: 'flex',
              flexDirection: 'row',
              gap: '8px',
            }}>
            <span>diff only</span>
            <Checkbox checked={diffOnly} onClick={() => setDiffOnly(v => !v)} />
          </div>
        </GridCell>

        {/* Model Rows */}
        {Object.entries(modelProps).map(([prop, modelData]) => {
          if (diffOnly && !propsWithDifferences.includes(prop)) {
            return null;
          }
          return (
            <React.Fragment key={prop}>
              <GridCell
                style={{
                  gridColumnEnd: 'span 2',
                  fontWeight: 'bold',
                  textAlign: 'right',
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
          const uniqueScorerRefs = Array.from(
            new Set(Object.values(def.evalCallIdToScorerRef))
          );
          const scorersAreComparable = uniqueScorerRefs.length === 1;
          const scorerRefParsed = parseRefMaybe(
            uniqueScorerRefs[0]
          ) as WeaveObjectRef | null;
          return (
            <React.Fragment key={key}>
              <GridCell
                style={{
                  gridColumnEnd: 'span 2',
                  borderTop: '1px solid #ccc',
                  fontWeight: 'bold',
                  textAlign: 'left',
                }}>
                {scorersAreComparable ? (
                  scorerRefParsed ? (
                    <SmallRef objRef={scorerRefParsed} />
                  ) : (
                    def.scorerName ?? ''
                  )
                ) : (
                  <Alert severity="warning">
                    <Tooltip title={VARIATION_WARNING_EXPLAINATION}>
                      <div
                        style={{
                          whiteSpace: 'nowrap',
                        }}>
                        {VARIATION_WARNING_TITLE}
                      </div>
                    </Tooltip>
                  </Alert>
                )}
              </GridCell>
              {evalCallIds.map((evalCallId, mNdx) => {
                const innerScorerRefParsed = parseRefMaybe(
                  def.evalCallIdToScorerRef[evalCallId]
                ) as WeaveObjectRef | null;
                return (
                  <GridCell
                    style={{
                      borderTop: '1px solid #ccc',
                      display: 'flex',
                      alignItems: 'center',
                    }}>
                    {!scorersAreComparable &&
                      (innerScorerRefParsed != null ? (
                        <SmallRef objRef={innerScorerRefParsed} />
                      ) : (
                        <NotApplicable />
                      ))}
                  </GridCell>
                );
              })}

              {Object.keys(def.metrics).map((metricKey, metricNdx) => {
                return (
                  <React.Fragment key={metricKey}>
                    <GridCell
                      style={{
                        gridColumnEnd: 'span 2',
                        borderBottom:
                          metricNdx === Object.keys(def.metrics).length - 1
                            ? '1px solid #ccc'
                            : '',
                        fontWeight: 'bold',
                        textAlign: 'right',
                        textOverflow: 'ellipsis',
                      }}>
                      {def.metrics[metricKey].displayName}
                    </GridCell>
                    {evalCallIds.map((evalCallId, mNdx) => {
                      const baseline =
                        def.metrics[metricKey].evalScores[
                          props.state.baselineEvaluationCallId
                        ];
                      const value =
                        def.metrics[metricKey].evalScores[evalCallId];
                      return (
                        <GridCell
                          key={evalCallId}
                          style={{
                            borderBottom:
                              metricNdx === Object.keys(def.metrics).length - 1
                                ? '1px solid #ccc'
                                : '',
                          }}>
                          {value != null ? (
                            <HorizontalBox
                              style={{
                                alignItems: 'center',
                              }}>
                              <span
                                style={{
                                  minWidth: '70px',
                                }}>
                                <ValueViewNumber
                                  fractionDigits={SIGNIFICANT_DIGITS}
                                  value={value}
                                />
                                {def.metrics[metricKey].unit}
                              </span>
                              <ComparisonPill
                                value={value}
                                baseline={baseline}
                                metricUnit={def.metrics[metricKey].unit}
                                metricLowerIsBetter={
                                  def.metrics[metricKey].lowerIsBetter
                                }
                              />
                            </HorizontalBox>
                          ) : (
                            <NotApplicable />
                          )}
                        </GridCell>
                      );
                    })}
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

export const ComparisonPill: React.FC<{
  value: number | undefined;
  baseline: number | undefined;
  metricUnit: string;
  metricLowerIsBetter?: boolean;
}> = ({value, baseline, metricUnit, metricLowerIsBetter}) => {
  const diff = (value ?? 0) - (baseline ?? 0);
  const diffFixed = Number.isInteger(diff)
    ? diff.toLocaleString()
    : diff.toFixed(SIGNIFICANT_DIGITS);
  const showPill = diff !== 0 && value != null && baseline != null;
  let color: TagColorName = 'moon';

  if (diff > 0) {
    if (!metricLowerIsBetter) {
      color = 'green';
    } else {
      color = 'red';
    }
  } else if (diff < 0) {
    if (!metricLowerIsBetter) {
      color = 'red';
    } else {
      color = 'green';
    }
  } else {
    color = 'moon';
  }
  if (!showPill) {
    return <></>;
  }
  return (
    <Pill
      label={(diff > 0 ? '+' : '') + diffFixed + metricUnit}
      color={color}
    />
  );
};
