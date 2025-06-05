import {Box} from '@material-ui/core';
import {Button} from '@wandb/weave/components/Button';
import {IconOnlyPill} from '@wandb/weave/components/Tag';
import {Tailwind} from '@wandb/weave/components/Tailwind';
import {Tooltip} from '@wandb/weave/components/Tooltip';
import _ from 'lodash';
import React, {useEffect, useMemo, useState} from 'react';
import styled from 'styled-components';

import {
  MOON_100,
  MOON_300,
} from '../../../../../../../../../common/css/color.styles';
import {parseRefMaybe, WeaveObjectRef} from '../../../../../../../../../react';
import {Checkbox} from '../../../../../../../..';
import {Pill, TagColorName} from '../../../../../../../../Tag';
import {CellValue} from '../../../../../../Browse2/CellValue';
import {CellValueBoolean} from '../../../../../../Browse2/CellValueBoolean';
import {NotApplicable} from '../../../../../NotApplicable';
import {SmallRef} from '../../../../../smallRef/SmallRef';
import {ValueViewNumber} from '../../../../CallPage/ValueViewNumber';
import {useGetTraceServerClientContext} from '../../../../wfReactInterface/traceServerClientContext';
import {ComputedCallStatusType} from '../../../../wfReactInterface/traceServerClientTypes';
import {projectIdFromParts} from '../../../../wfReactInterface/tsDataModelHooks';
import {useCompareEvaluationsState} from '../../compareEvaluationsContext';
import {
  buildCompositeMetricsMap,
  CompositeScoreMetrics,
  DERIVED_SCORER_REF_PLACEHOLDER,
  evalCallIdToScorerRefs,
  resolveDimension,
} from '../../compositeMetricsUtil';
import {
  SIGNIFICANT_DIGITS,
  STANDARD_BORDER,
  STANDARD_PADDING,
} from '../../ecpConstants';
import {
  EvaluationComparisonState,
  getOrderedCallIds,
  getOrderedModelRefs,
} from '../../ecpState';
import {resolveSummaryMetricResultForEvaluateCall} from '../../ecpUtil';
import {usePeekCall} from '../../hooks';
import {filterLatestCallIdsPerModelDataset} from '../../latestEvaluationUtil';
import {HorizontalBox} from '../../Layout';
import {
  EvaluationCallLink,
  EvaluationDatasetLink,
  EvaluationModelLink,
} from '../ComparisonDefinitionSection/EvaluationDefinition';

export const SCORER_VARIATION_WARNING_TITLE = 'Scoring inconsistency detected';
export const SCORER_VARIATION_WARNING_EXPLANATION =
  'The scoring logic varies between evaluations. Take precaution when comparing results.';

const DATASET_VARIATION_WARNING_EXPLANATION =
  'The dataset varies between evaluations therefore aggregate metrics may not be directly comparable. Examples are limited to the intersection of the datasets.';

const GridCell = styled.div<{
  button?: boolean;
}>`
  padding: 6px 16px;
  min-width: 100px;
  font-size: 14px;
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
GridCell.displayName = 'S.GridCell';

export const ScorecardSection: React.FC<{
  state: EvaluationComparisonState;
  initialExpanded?: boolean;
  sortColumnsByDatasetAndModel?: boolean;
  disableBaselineStats?: boolean;
}> = props => {
  const [isExpanded, setIsExpanded] = useState(props.initialExpanded ?? false);

  const toggleExpanded = () => {
    setIsExpanded(!isExpanded);
  };

  return (
    <div
      style={{backgroundColor: MOON_100, width: '100%', paddingBottom: '16px'}}>
      <Box
        sx={{
          display: 'flex',
          alignItems: 'center',
          borderTop: `1px solid ${MOON_300}`,
          borderBottom: !isExpanded ? `1px solid ${MOON_300}` : 'none',
          paddingLeft: STANDARD_PADDING,
          paddingRight: STANDARD_PADDING,
          paddingTop: '8px',
          paddingBottom: '8px',
        }}
        style={{
          backgroundColor: 'transparent',
        }}>
        <Tailwind>
          <div className="flex items-center gap-8">
            <Button
              variant="ghost"
              icon={isExpanded ? 'chevron-down' : 'chevron-next'}
              size="small"
              onClick={e => {
                e.stopPropagation();
                toggleExpanded();
              }}
            />
            <h3 className="m-0 text-lg">Evaluation details</h3>
          </div>
        </Tailwind>
      </Box>
      {isExpanded && (
        <Box
          sx={{
            borderTop: 'none',
            borderRadius: '0 0 8px 8px',
          }}>
          <ScorecardContent
            state={props.state}
            sortColumnsByDatasetAndModel={props.sortColumnsByDatasetAndModel}
            disableBaselineStats={props.disableBaselineStats}
          />
        </Box>
      )}
    </div>
  );
};

// Hook to fetch call statuses for evaluation calls in compare evaluations
const useEvaluationCallStatuses = (
  entity: string,
  project: string,
  evalCallIds: string[]
): Record<string, ComputedCallStatusType> => {
  const getClient = useGetTraceServerClientContext();
  const [callStatuses, setCallStatuses] = useState<
    Record<string, ComputedCallStatusType>
  >({});

  useEffect(() => {
    if (evalCallIds.length === 0) {
      setCallStatuses({});
      return;
    }

    const client = getClient();
    const fetchCallStatuses = async () => {
      try {
        const response = await client.callsStreamQuery({
          project_id: projectIdFromParts({entity, project}),
          filter: {
            call_ids: evalCallIds,
          },
          limit: evalCallIds.length,
        });

        const statuses: Record<string, ComputedCallStatusType> = {};
        response.calls.forEach(call => {
          // Extract status from the call summary or default to 'success' if finished
          const status =
            call.summary?.status || (call.ended_at ? 'success' : 'running');
          statuses[call.id] = status;
        });

        setCallStatuses(statuses);
      } catch (error) {
        console.error('Error fetching call statuses:', error);
        setCallStatuses({});
      }
    };

    fetchCallStatuses();
  }, [entity, project, evalCallIds, getClient]);

  return callStatuses;
};

const ScorecardContent: React.FC<{
  state: EvaluationComparisonState;
  sortColumnsByDatasetAndModel?: boolean;
  disableBaselineStats?: boolean;
}> = props => {
  const {hiddenEvaluationIds, filterToLatestEvaluationsPerModel} =
    useCompareEvaluationsState();

  const evalCallIds = useMemo(() => {
    const allCallIds = getOrderedCallIds(props.state).filter(
      id => !hiddenEvaluationIds.has(id)
    );

    let filteredCallIds = allCallIds;

    // Only apply latest evaluation filtering if we're in leaderboard mode
    if (filterToLatestEvaluationsPerModel) {
      // Filter to keep only the latest evaluation for each model-dataset combination
      filteredCallIds = filterLatestCallIdsPerModelDataset(
        allCallIds,
        props.state.summary.evaluationCalls,
        props.state.summary.evaluations,
        {},
        true
      );
    }

    // Apply sorting by dataset name and then model name if requested
    if (props.sortColumnsByDatasetAndModel) {
      filteredCallIds = filteredCallIds.slice().sort((a, b) => {
        const evaluationCallA = props.state.summary.evaluationCalls[a];
        const evaluationCallB = props.state.summary.evaluationCalls[b];

        const evaluationA =
          props.state.summary.evaluations[evaluationCallA.evaluationRef];
        const evaluationB =
          props.state.summary.evaluations[evaluationCallB.evaluationRef];

        const modelA = props.state.summary.models[evaluationCallA.modelRef];
        const modelB = props.state.summary.models[evaluationCallB.modelRef];

        // Extract dataset names for comparison
        const datasetRefA = evaluationA?.datasetRef;
        const datasetRefB = evaluationB?.datasetRef;

        const datasetNameA = datasetRefA
          ? (parseRefMaybe(datasetRefA) as WeaveObjectRef)?.artifactName ||
            datasetRefA
          : '';
        const datasetNameB = datasetRefB
          ? (parseRefMaybe(datasetRefB) as WeaveObjectRef)?.artifactName ||
            datasetRefB
          : '';

        // Extract model names for comparison
        const modelNameA =
          (modelA?.properties?.name as string) || evaluationCallA.modelRef;
        const modelNameB =
          (modelB?.properties?.name as string) || evaluationCallB.modelRef;

        // First sort by dataset name
        const datasetComparison = datasetNameA.localeCompare(datasetNameB);
        if (datasetComparison !== 0) {
          return datasetComparison;
        }

        // Then sort by model name
        return modelNameA.localeCompare(modelNameB);
      });
    }

    return filteredCallIds;
  }, [
    props.state,
    hiddenEvaluationIds,
    filterToLatestEvaluationsPerModel,
    props.sortColumnsByDatasetAndModel,
  ]);

  const modelRefs = useMemo(() => {
    // Get all model refs from visible evaluations only
    const visibleEvalCalls = evalCallIds.map(
      id => props.state.summary.evaluationCalls[id]
    );
    const visibleModelRefs = new Set(
      visibleEvalCalls.map(call => call.modelRef)
    );
    // Keep the ordering from getOrderedModelRefs but filter to only visible ones
    return getOrderedModelRefs(props.state).filter(ref =>
      visibleModelRefs.has(ref)
    );
  }, [props.state, evalCallIds]);

  const datasetRefs = useMemo(() => {
    // Use filtered evalCallIds instead of all evaluations to respect filtering
    return evalCallIds
      .map(callId => {
        const evaluationCall = props.state.summary.evaluationCalls[callId];
        if (!evaluationCall) return null;
        const evaluationObj =
          props.state.summary.evaluations[evaluationCall.evaluationRef];
        return evaluationObj?.datasetRef;
      })
      .filter((ref): ref is string => ref != null);
  }, [
    evalCallIds,
    props.state.summary.evaluationCalls,
    props.state.summary.evaluations,
  ]);

  const datasetVariation = useMemo(() => {
    // Extract dataset names and versions to check for version variations
    const datasetVersionMap: {[datasetName: string]: Set<string>} = {};

    datasetRefs.forEach(ref => {
      // Parse the ref to extract name and version
      const parsed = parseRefMaybe(ref) as WeaveObjectRef;
      if (parsed && parsed.artifactName && parsed.artifactVersion) {
        const datasetName = parsed.artifactName;
        const datasetVersion = parsed.artifactVersion;

        if (!datasetVersionMap[datasetName]) {
          datasetVersionMap[datasetName] = new Set();
        }
        datasetVersionMap[datasetName].add(datasetVersion);
      }
    });

    // Check if any dataset has multiple versions
    return Object.values(datasetVersionMap).some(versions => versions.size > 1);
  }, [datasetRefs]);

  const modelProps = useMemo(() => {
    const propsRes: {[prop: string]: {[ref: string]: any}} = {};
    modelRefs.forEach(ref => {
      const model = props.state.summary.models[ref];
      Object.keys(model?.properties ?? {}).forEach(prop => {
        if (!propsRes[prop]) {
          propsRes[prop] = {};
        }
        propsRes[prop][ref] = model?.properties?.[prop];
      });
    });

    // Make sure predict op is last
    modelRefs.forEach(ref => {
      const model = props.state.summary.models[ref];
      if (!propsRes.predict) {
        propsRes.predict = {};
      }
      propsRes.predict[ref] = model?.predictOpRef;
    });

    return propsRes;
  }, [modelRefs, props.state.summary.models]);
  const propsWithDifferences = useMemo(() => {
    return Object.keys(modelProps).filter(prop => {
      const values = Object.values(modelProps[prop]);
      return values.some((value, i) => i > 0 && !_.isEqual(value, values[0]));
    });
  }, [modelProps]);
  const [diffOnly, setDiffOnly] = React.useState(true);

  const compositeSummaryMetrics = useMemo(() => {
    return buildCompositeMetricsMap(
      props.state.summary,
      'summary',
      props.state.selectedMetrics
    );
  }, [props.state]);

  // Fetch call statuses for running indicators
  const callStatuses = useEvaluationCallStatuses(
    props.state.summary.entity,
    props.state.summary.project,
    evalCallIds
  );

  const onCallClick = usePeekCall(
    props.state.summary.entity,
    props.state.summary.project
  );

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
      <div
        style={{
          display: 'grid',
          gridTemplateColumns,
          border: STANDARD_BORDER,
          overflow: 'auto',
          backgroundColor: 'white',
          borderRadius: '8px',
        }}>
        {/* Header Row */}
        <GridCell
          style={{
            fontWeight: '600',
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
                fontWeight: '600',
              }}>
              <EvaluationCallLink
                callId={evalCallId}
                state={props.state}
                callStatus={callStatuses[evalCallId]}
              />
            </GridCell>
          );
        })}
        <GridCell
          style={{
            fontWeight: '600',
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
                fontWeight: '600',
              }}>
              <EvaluationModelLink callId={evalCallId} state={props.state} />
            </GridCell>
          );
        })}
        <>
          <GridCell
            style={{
              fontWeight: '600',
              textAlign: 'right',
              gridColumnEnd: 'span 2',
            }}>
            {datasetVariation ? (
              <div
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: '8px',
                  justifyContent: 'flex-end',
                }}>
                Dataset
                <Tooltip
                  trigger={
                    <span>
                      <IconOnlyPill
                        icon="warning"
                        color="gold"
                        style={{flexShrink: 1}}
                      />
                    </span>
                  }
                  content={DATASET_VARIATION_WARNING_EXPLANATION}
                />
              </div>
            ) : (
              'Dataset'
            )}
          </GridCell>
          {evalCallIds.map(evalCallId => {
            return (
              <GridCell
                key={evalCallId}
                style={{
                  fontWeight: '600',
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
        <GridCell
          style={{
            gridColumnEnd: 'span ' + (evalCallIds.length + 2),
            backgroundColor: MOON_100,
            fontWeight: 600,
            fontSize: '16px',
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
            <span style={{fontSize: '14px'}}>Diff only</span>
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
                  fontWeight: '600',
                  textAlign: 'right',
                  textOverflow: 'ellipsis',
                }}>
                {prop}
              </GridCell>
              {evalCallIds.map((evalCallId, mNdx) => {
                const model =
                  props.state.summary.evaluationCalls[evalCallId].modelRef;
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
            fontWeight: 600,
            fontSize: '16px',
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
                      fontWeight: '600',
                      textAlign: 'left',
                    }}>
                    {scorersAreComparable ? (
                      scorerRefParsed && <SmallRef objRef={scorerRefParsed} />
                    ) : (
                      <div
                        style={{
                          display: 'flex',
                          alignItems: 'center',
                          gap: '8px',
                          justifyContent: 'flex-end',
                        }}>
                        Scorer
                        <Tooltip
                          trigger={
                            <span>
                              <IconOnlyPill
                                icon="warning"
                                color="gold"
                                style={{flexShrink: 1}}
                              />
                            </span>
                          }
                          content={SCORER_VARIATION_WARNING_EXPLANATION}
                        />
                      </div>
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
                        fontWeight: '600',
                        textAlign: 'right',
                        textOverflow: 'ellipsis',
                      }}>
                      {metricKey}
                    </GridCell>
                    {evalCallIds.map((evalCallId, mNdx) => {
                      // Use the first visible evaluation as baseline
                      const baselineCallId = evalCallIds[0];
                      const baseline = resolveSummaryMetricResult(
                        baselineCallId,
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
                              {dataIsNumber && !props.disableBaselineStats && (
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
        state.summary.evaluationCalls[evalCallId]
      )
    : undefined;
  return baseline;
};
