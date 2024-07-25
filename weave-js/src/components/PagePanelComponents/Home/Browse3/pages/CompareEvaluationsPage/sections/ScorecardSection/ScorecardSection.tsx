import {Box, Tooltip} from '@material-ui/core';
import {Alert} from '@mui/material';
import _ from 'lodash';
import React, {useMemo} from 'react';
import styled from 'styled-components';

import {
  MOON_100,
  MOON_300,
  MOON_600,
} from '../../../../../../../../common/css/color.styles';
import {WeaveObjectRef} from '../../../../../../../../react';
import {Checkbox} from '../../../../../../..';
import {Pill, TagColorName} from '../../../../../../../Tag';
import {CellValue} from '../../../../../Browse2/CellValue';
import {CellValueBoolean} from '../../../../../Browse2/CellValueBoolean';
import {NotApplicable} from '../../../../../Browse2/NotApplicable';
import {parseRefMaybe, SmallRef} from '../../../../../Browse2/SmallRef';
import {ValueViewNumber} from '../../../CallPage/ValueViewNumber';
import {
  CompositeScoreMetrics,
  DERIVED_SCORER_REF_PLACEHOLDER,
  evalCallIdToScorerRefs,
  resolveDimension,
} from '../../compositeMetricsUtil';
import {buildCompositeMetricsMap} from '../../compositeMetricsUtil';
import {
  BOX_RADIUS,
  STANDARD_BORDER,
  STANDARD_PADDING,
} from '../../ecpConstants';
import {SIGNIFICANT_DIGITS} from '../../ecpConstants';
import {getOrderedCallIds, getOrderedModelRefs} from '../../ecpState';
import {EvaluationComparisonState} from '../../ecpState';
import {resolveSummaryMetricResultForEvaluateCall} from '../../ecpUtil';
import {usePeekCall} from '../../hooks';
import {HorizontalBox} from '../../Layout';
import {
  EvaluationCallLink,
  EvaluationDatasetLink,
  EvaluationModelLink,
} from '../ComparisonDefinitionSection/EvaluationDefinition';

export const SCORER_VARIATION_WARNING_TITLE = 'Scoring inconsistency detected';
export const SCORER_VARIATION_WARNING_EXPLANATION =
  'The scoring logic varies between evaluations. Take precaution when comparing results.';

const DATASET_VARIATION_WARNING_TITLE = 'Dataset inconsistency detected';
const DATASET_VARIATION_WARNING_EXPLANATION =
  'The dataset varies between evaluations therefore aggregate metrics may not be directly comparable. Examples are limited to the intersection of the datasets.';

const GridCell = styled.div<{
  button?: boolean;
}>`
  padding: 6px 16px;
  min-width: 100px;
  ${props =>
    props.button &&
    `
    cursor: pointer;
    transition: background-color 0.2s;
    &:hover {
      background-color: ${MOON_300};
    }
  `}
`;

export const ScorecardSection: React.FC<{
  state: EvaluationComparisonState;
}> = props => {
  const modelRefs = useMemo(
    () => getOrderedModelRefs(props.state),
    [props.state]
  );
  const datasetRefs = useMemo(
    () => Object.values(props.state.data.evaluations).map(e => e.datasetRef),
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
      return values.some((value, i) => i > 0 && !_.isEqual(value, values[0]));
    });
  }, [modelProps]);
  const [diffOnly, setDiffOnly] = React.useState(true);

  const compositeSummaryMetrics = useMemo(() => {
    return buildCompositeMetricsMap(props.state.data, 'summary');
  }, [props.state]);

  const onCallClick = usePeekCall(
    props.state.data.entity,
    props.state.data.project
  );

  const datasetVariation = Array.from(new Set(datasetRefs)).length > 1;

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
        {datasetVariation && (
          <>
            <GridCell
              style={{
                fontWeight: 'bold',
                textAlign: 'right',
                gridColumnEnd: 'span 2',
              }}>
              <Alert
                severity="warning"
                style={{
                  paddingTop: 0,
                  paddingBottom: 0,
                }}>
                <Tooltip title={DATASET_VARIATION_WARNING_EXPLANATION}>
                  <div
                    style={{
                      whiteSpace: 'nowrap',
                    }}>
                    {DATASET_VARIATION_WARNING_TITLE}
                  </div>
                </Tooltip>
              </Alert>
            </GridCell>
            {evalCallIds.map(evalCallId => {
              return (
                <GridCell
                  key={evalCallId}
                  style={{
                    fontWeight: 'bold',
                    display: 'flex',
                    alignItems: 'center',
                  }}>
                  <EvaluationDatasetLink
                    callId={evalCallId}
                    state={props.state}
                  />
                </GridCell>
              );
            })}
          </>
        )}
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
                      <CellValue value={modelData[model]} />
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
        {Object.entries(compositeSummaryMetrics).map(([groupName, group]) => {
          const evalCallIdToScorerRef = evalCallIdToScorerRefs(group);
          const uniqueScorerRefs = Array.from(
            new Set(Object.values(evalCallIdToScorerRef))
          );
          const scorersAreComparable = uniqueScorerRefs.length === 1;
          const scorerRefParsed = parseRefMaybe(
            uniqueScorerRefs[0]
          ) as WeaveObjectRef | null;
          return (
            <React.Fragment key={groupName}>
              {groupName !== DERIVED_SCORER_REF_PLACEHOLDER && (
                <>
                  <GridCell
                    style={{
                      gridColumnEnd: 'span 2',
                      borderTop: '1px solid #ccc',
                      fontWeight: 'bold',
                      textAlign: 'left',
                    }}>
                    {scorersAreComparable ? (
                      scorerRefParsed && <SmallRef objRef={scorerRefParsed} />
                    ) : (
                      <Alert
                        severity="warning"
                        style={{
                          paddingTop: 0,
                          paddingBottom: 0,
                        }}>
                        <Tooltip title={SCORER_VARIATION_WARNING_EXPLANATION}>
                          <div
                            style={{
                              whiteSpace: 'nowrap',
                            }}>
                            {SCORER_VARIATION_WARNING_TITLE}
                          </div>
                        </Tooltip>
                      </Alert>
                    )}
                  </GridCell>
                  {evalCallIds.map((evalCallId, mNdx) => {
                    const innerScorerRefParsed = parseRefMaybe(
                      evalCallIdToScorerRef[evalCallId]
                    ) as WeaveObjectRef | null;
                    return (
                      <GridCell
                        key={evalCallId}
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
                </>
              )}
              {Object.keys(group.metrics).map((metricKey, metricNdx) => {
                return (
                  <React.Fragment key={metricKey}>
                    <GridCell
                      style={{
                        gridColumnEnd: 'span 2',
                        borderBottom:
                          metricNdx === Object.keys(group.metrics).length - 1
                            ? '1px solid #ccc'
                            : '',
                        fontWeight: 'bold',
                        textAlign: 'right',
                        textOverflow: 'ellipsis',
                      }}>
                      {metricKey}
                    </GridCell>
                    {evalCallIds.map((evalCallId, mNdx) => {
                      const baseline = resolveSummaryMetricResult(
                        props.state.baselineEvaluationCallId,
                        groupName,
                        metricKey,
                        compositeSummaryMetrics,
                        props.state
                      )?.value;
                      const metric = resolveSummaryMetricResult(
                        evalCallId,
                        groupName,
                        metricKey,
                        compositeSummaryMetrics,
                        props.state
                      );
                      const value = metric?.value;
                      const sourceCallId = metric?.sourceCallId;

                      const valueIsNumber = typeof value === 'number';
                      const dataIsNumber =
                        valueIsNumber && typeof baseline === 'number';

                      const onClick = sourceCallId
                        ? () => onCallClick(sourceCallId)
                        : undefined;

                      return (
                        <GridCell
                          key={evalCallId}
                          style={{
                            borderBottom:
                              metricNdx ===
                              Object.keys(group.metrics).length - 1
                                ? '1px solid #ccc'
                                : '',
                          }}
                          onClick={onClick}
                          button={!!onClick}>
                          {value != null ? (
                            <HorizontalBox
                              style={{
                                alignItems: 'center',
                              }}>
                              <HorizontalBox
                                style={{
                                  minWidth: '70px',
                                  gap: '4px',
                                }}>
                                {valueIsNumber ? (
                                  <ValueViewNumber
                                    value={value}
                                    fractionDigits={4}
                                  />
                                ) : (
                                  <CellValueBoolean value={value} />
                                )}
                                {group.metrics[metricKey]
                                  .scorerAgnosticMetricDef.unit ?? ''}
                              </HorizontalBox>
                              {dataIsNumber && (
                                <ComparisonPill
                                  value={value}
                                  baseline={baseline}
                                  metricUnit={
                                    group.metrics[metricKey]
                                      .scorerAgnosticMetricDef.unit ?? ''
                                  }
                                  metricLowerIsBetter={
                                    group.metrics[metricKey]
                                      .scorerAgnosticMetricDef.shouldMinimize ??
                                    false
                                  }
                                />
                              )}
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

const resolveSummaryMetricResult = (
  evalCallId: string,
  groupName: string,
  metricKey: string,
  compositeSummaryMetrics: CompositeScoreMetrics,
  state: EvaluationComparisonState
) => {
  const baselineDimension = resolveDimension(
    compositeSummaryMetrics,
    evalCallId,
    groupName,
    metricKey
  );
  const baseline = baselineDimension
    ? resolveSummaryMetricResultForEvaluateCall(
        baselineDimension,
        state.data.evaluationCalls[evalCallId]
      )
    : undefined;
  return baseline;
};
