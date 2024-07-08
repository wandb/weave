import {Box} from '@material-ui/core';
import {Circle} from '@mui/icons-material';
import _ from 'lodash';
import React, {useCallback, useMemo} from 'react';
import {useHistory} from 'react-router-dom';
import styled from 'styled-components';

import {
  MOON_100,
  MOON_300,
  MOON_800,
} from '../../../../../../../../common/css/color.styles';
import {parseRef, WeaveObjectRef} from '../../../../../../../../react';
import {Button} from '../../../../../../../Button';
import {CellValue} from '../../../../../Browse2/CellValue';
import {NotApplicable} from '../../../../../Browse2/NotApplicable';
import {parseRefMaybe, SmallRef} from '../../../../../Browse2/SmallRef';
import {useWeaveflowRouteContext} from '../../../../context';
import {ValueViewNumber} from '../../../CallPage/ValueViewNumber';
import {CallLink} from '../../../common/Links';
import {isRef} from '../../../common/util';
import {TraceCallSchema} from '../../../wfReactInterface/traceServerClient';
import {useCompareEvaluationsState} from '../../compareEvaluationsContext';
import {CIRCLE_SIZE, SIGNIFICANT_DIGITS} from '../../ecpConstants';
import {EvaluationComparisonState} from '../../ecpTypes';
import {
  adjustValueForDisplay,
  dimensionId,
  dimensionLabel,
  dimensionShouldMinimize,
  dimensionUnit,
} from '../../ecpUtil';
import {HorizontalBox, VerticalBox} from '../../Layout';
import {ComparisonPill} from '../ScorecardSection/ScorecardSection';
import {useFilteredAggregateRows} from './exampleCompareSectionUtil';

const MIN_OUTPUT_WIDTH = 500;

const GridCell = styled.div<{
  cols?: number;
  rows?: number;
  noPad?: boolean;
  button?: boolean;
}>`
  border: 1px solid ${MOON_300};
  grid-column-end: span ${props => props.cols || 1};
  grid-row-end: span ${props => props.rows || 1};
  padding: ${props => (props.noPad ? '0px' : '8px')};
  // Hover should show click mouse icon
  // and slowly highlight blue like a button
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

const GridContainer = styled.div<{numColumns: number}>`
  display: grid;
  /* grid-template-columns: ${props => '1fr '.repeat(props.numColumns)}; */
  /* grid-gap: 10px; */
`;

export const ExampleCompareSection: React.FC<{
  state: EvaluationComparisonState;
}> = props => {
  const {filteredRows, outputColumnKeys, leafDims} = useFilteredAggregateRows(
    props.state
  );
  const {setSelectedInputDigest} = useCompareEvaluationsState();
  const targetIndex = useMemo(() => {
    const selectedDigest = props.state.selectedInputDigest;
    if (selectedDigest) {
      const found = filteredRows.findIndex(
        row => row.inputDigest === selectedDigest
      );
      if (found !== -1) {
        return found;
      }
    }
    return 0;
  }, [filteredRows, props.state.selectedInputDigest]);

  const target = useMemo(() => {
    return filteredRows[targetIndex];
  }, [filteredRows, targetIndex]);

  const sortedScorers = _.sortBy(
    Object.values(props.state.data.scorerMetricDimensions),
    k => k.scorerDef.scorerOpOrObjRef
  );
  const uniqueScorerRefs = _.uniq(
    sortedScorers.map(v => v.scorerDef.scorerOpOrObjRef)
  );
  const derivedScorers = Object.values(
    props.state.data.derivedMetricDimensions
  );

  const leftRef = React.useRef<HTMLDivElement>(null);

  const [selectedTrials, setSelectedTrials] = React.useState<{
    [evalCallId: string]: number;
  }>({});

  const history = useHistory();
  const {peekingRouter} = useWeaveflowRouteContext();

  const onScorerClick = useCallback(
    (scorerCall: TraceCallSchema) => {
      const [entityName, projectName] = scorerCall.project_id.split('/');
      const callId = scorerCall.id;
      const to = peekingRouter.callUIUrl(entityName, projectName, '', callId);
      history.push(to);
    },
    [history, peekingRouter]
  );

  if (target == null) {
    return <div>Filter resulted in 0 rows</div>;
  }

  const inputRef = parseRef(target.inputRef) as WeaveObjectRef;
  const NUM_SCORERS = uniqueScorerRefs.length;
  const NUM_DERIVED = derivedScorers.length;
  const NUM_METRICS =
    NUM_DERIVED + Object.values(props.state.data.scorerMetricDimensions).length;
  const NUM_COLS =
    1 + // Input / Eval Title
    2; // Input Prop Key / Val

  const inputColumnKeys = Object.keys(target.input);
  const NUM_INPUT_PROPS = inputColumnKeys.length;
  const NUM_OUTPUT_KEYS = outputColumnKeys.length;
  const NUM_EVALS = leafDims.length;

  return (
    <VerticalBox
      sx={{
        height: '100%',

        gridGap: '0px',
      }}>
      <HorizontalBox
        sx={{
          justifyContent: 'space-between',
          alignItems: 'center',
          bgcolor: MOON_100,
          padding: '16px',
        }}>
        <HorizontalBox
          sx={{
            alignItems: 'center',
            flex: 1,
          }}>
          <Box
            style={{
              flex: 0,
            }}>
            <SmallRef objRef={inputRef} iconOnly />
          </Box>
          <Box
            style={{
              flex: 1,
            }}>
            {`Example ${targetIndex + 1} of ${filteredRows.length}`}
          </Box>
        </HorizontalBox>
        <Box>
          <Button
            className="mx-16"
            style={{
              marginLeft: '0px',
            }}
            size="small"
            disabled={targetIndex === 0}
            onClick={() => {
              setSelectedInputDigest(filteredRows[targetIndex - 1].inputDigest);
            }}
            icon="chevron-back"
          />

          <Button
            style={{
              marginLeft: '0px',
            }}
            disabled={targetIndex === filteredRows.length - 1}
            size="small"
            onClick={() => {
              setSelectedInputDigest(filteredRows[targetIndex + 1].inputDigest);
            }}
            icon="chevron-next"
          />
        </Box>
      </HorizontalBox>
      <GridContainer
        numColumns={NUM_COLS}
        style={{
          height: '100%',
          flex: 1,
          display: 'grid',
          overflow: 'auto',
          gridTemplateColumns: `repeat(2, min-content) auto`,
          gridTemplateRows: `repeat(${NUM_INPUT_PROPS}, min-content) min-content repeat(${NUM_OUTPUT_KEYS}, auto) min-content repeat(${NUM_METRICS}, min-content)`,
        }}>
        {_.range(NUM_INPUT_PROPS).map(ii => {
          const inputColumnKey = inputColumnKeys[ii];
          return (
            <React.Fragment key={inputColumnKey}>
              <GridCell
                cols={2}
                style={{
                  whiteSpace: 'nowrap',
                  left: 0,
                  position: 'sticky',
                  zIndex: 1,
                  backgroundColor: 'white',
                  textAlign: 'right',
                  fontWeight: 'bold',
                }}>
                {removePrefix(inputColumnKey, 'input.')}
              </GridCell>
              <GridCell>
                <ICValueView value={target.input[inputColumnKey]} />
              </GridCell>
            </React.Fragment>
          );
        })}
        <GridCell
          cols={2}
          rows={1 + NUM_OUTPUT_KEYS + 1 + NUM_METRICS}
          noPad
          style={{
            display: 'grid',
            gridTemplateRows: 'subgrid',
            gridTemplateColumns: 'subgrid',
            position: 'sticky',
            left: 0,
            zIndex: 3,
            backgroundColor: 'white',
            border: 'none',
          }}>
          <GridCell
            cols={2}
            style={{
              position: 'sticky',
              left: 0,
              top: 0,
              zIndex: 2,
              backgroundColor: MOON_100,
            }}></GridCell>

          {_.range(NUM_OUTPUT_KEYS).map(oi => {
            return (
              <React.Fragment key={outputColumnKeys[oi]}>
                <GridCell
                  cols={2}
                  style={{
                    whiteSpace: 'nowrap',
                    position: 'sticky',
                    left: 0,
                    zIndex: 1,
                    backgroundColor: 'white',
                    textAlign: 'right',
                    fontWeight: 'bold',
                  }}>
                  {removePrefix(outputColumnKeys[oi], 'output.')}
                </GridCell>
              </React.Fragment>
            );
          })}
          <GridCell
            cols={2}
            rows={NUM_METRICS + 1}
            noPad
            style={{
              display: 'grid',
              gridTemplateRows: 'subgrid',
              gridTemplateColumns: 'subgrid',
              position: 'sticky',
              bottom: 0,
              left: 0,
              zIndex: 3,
              backgroundColor: 'white',
              border: 'none',
            }}>
            <GridCell
              cols={2}
              style={{
                backgroundColor: MOON_100,
              }}>
              Metrics
            </GridCell>
            {_.range(NUM_SCORERS + 1).map(si => {
              const isScorerMetric = si < NUM_SCORERS;
              const dimensionsForThisScorer = isScorerMetric
                ? sortedScorers.filter(
                    s => s.scorerDef.scorerOpOrObjRef === uniqueScorerRefs[si]
                  )
                : derivedScorers;
              const NUM_METRICS_IN_SCORER = dimensionsForThisScorer.length;
              const scorerRef = uniqueScorerRefs[si];
              return (
                <React.Fragment key={isScorerMetric ? scorerRef : 'derived'}>
                  <GridCell
                    ref={leftRef}
                    rows={NUM_METRICS_IN_SCORER}
                    style={{
                      alignContent: 'center',
                    }}>
                    {isScorerMetric && (
                      <SmallRef
                        objRef={parseRef(scorerRef) as WeaveObjectRef}
                        iconOnly
                      />
                    )}
                  </GridCell>
                  {_.range(NUM_METRICS_IN_SCORER).map(mi => {
                    return (
                      <React.Fragment key={mi}>
                        <GridCell
                          style={{
                            whiteSpace: 'nowrap',
                            textAlign: 'right',
                            fontWeight: 'bold',
                          }}>
                          {dimensionLabel(dimensionsForThisScorer[mi])}
                        </GridCell>
                      </React.Fragment>
                    );
                  })}
                </React.Fragment>
              );
            })}
          </GridCell>
        </GridCell>
        <GridCell
          noPad
          style={{
            border: 'none',
            display: 'grid',
            gridTemplateRows: 'subgrid',
            gridTemplateColumns: `repeat(${NUM_EVALS}, min-content auto)`,
          }}
          rows={
            NUM_OUTPUT_KEYS +
            1 + // Eval Header
            1 + // Aggregate Metrics Header
            NUM_METRICS
          }>
          {_.range(NUM_EVALS).map(ei => {
            const currEvalCallId = leafDims[ei];
            const trialsForThisEval = target.originalRows.filter(
              row => row.evaluationCallId === currEvalCallId
            );
            const selectedTrial =
              trialsForThisEval[selectedTrials[currEvalCallId] || 0];
            const trialPredict =
              selectedTrial.predictAndScore._rawPredictTraceData;
            const [trialEntity, trialProject] =
              trialPredict?.project_id.split('/') ?? [];
            const trialOpName = parseRefMaybe(
              trialPredict?.op_name ?? ''
            )?.artifactName;
            const trialCallId = trialPredict?.id;
            const evaluationCall =
              props.state.data.evaluationCalls[currEvalCallId];

            return (
              <GridCell
                key={currEvalCallId}
                cols={2}
                style={{
                  minWidth: MIN_OUTPUT_WIDTH,
                  position: 'sticky',
                  top: 0,
                  zIndex: 1,
                  backgroundColor: MOON_100,
                }}>
                {trialEntity && trialProject && trialOpName && trialCallId && (
                  <CallLink
                    entityName={trialEntity}
                    projectName={trialProject}
                    opName={trialOpName}
                    callId={trialCallId}
                    icon={
                      <Circle
                        sx={{
                          color: evaluationCall.color,
                          height: CIRCLE_SIZE,
                        }}
                      />
                    }
                    color={MOON_800}
                  />
                )}
              </GridCell>
            );
          })}

          {_.range(NUM_OUTPUT_KEYS).map(oi => {
            return _.range(NUM_EVALS).map(ei => {
              const currEvalCallId = leafDims[ei];
              const trialsForThisEval = target.originalRows.filter(
                row => row.evaluationCallId === currEvalCallId
              );
              const selectedTrial =
                trialsForThisEval[selectedTrials[currEvalCallId] || 0];

              return (
                <GridCell key={currEvalCallId} cols={2}>
                  <ICValueView
                    value={
                      (selectedTrial?.output?.[outputColumnKeys[oi]] ?? {})[
                        currEvalCallId
                      ]
                    }
                  />
                </GridCell>
              );
            });
          })}
          {_.range(NUM_EVALS).map(ei => {
            const currEvalCallId = leafDims[ei];
            const trialsForThisEval = target.originalRows.filter(
              row => row.evaluationCallId === currEvalCallId
            );
            const selectedTrialNdx = selectedTrials[currEvalCallId] || 0;
            const NUM_TRIALS = trialsForThisEval.length;

            return (
              <GridCell
                key={currEvalCallId}
                cols={2}
                rows={NUM_METRICS + 1}
                noPad
                style={{
                  display: 'grid',
                  gridTemplateRows: 'subgrid',
                  gridTemplateColumns: `repeat(${NUM_TRIALS + 1}, auto)`,
                  overflowX: 'auto',
                  position: 'sticky',
                  bottom: 0,
                  zIndex: 1,
                  backgroundColor: 'white',
                  border: 'none',
                }}>
                <GridCell
                  style={{
                    position: 'sticky',
                    left: 0,
                    zIndex: 1,
                    backgroundColor: MOON_100,
                  }}>
                  Agg Metrics \ Trials
                </GridCell>
                {_.range(NUM_TRIALS).map(ti => {
                  return (
                    <GridCell
                      key={ti}
                      style={{
                        textAlign: 'center',
                      }}>
                      <Button
                        size="small"
                        variant={
                          selectedTrialNdx === ti ? 'primary' : 'secondary'
                        }
                        onClick={() => {
                          setSelectedTrials(curr => {
                            return {
                              ...curr,
                              [currEvalCallId]: ti,
                            };
                          });
                        }}
                        icon="show-visible">
                        {ti.toString()}
                      </Button>
                    </GridCell>
                  );
                })}
                {_.range(NUM_SCORERS + 1).map(si => {
                  const isScorerMetric = si < NUM_SCORERS;

                  const dimensionsForThisScorer = isScorerMetric
                    ? sortedScorers.filter(
                        s =>
                          s.scorerDef.scorerOpOrObjRef === uniqueScorerRefs[si]
                      )
                    : derivedScorers;
                  const NUM_METRICS_IN_SCORER = dimensionsForThisScorer.length;
                  return (
                    <React.Fragment
                      key={isScorerMetric ? uniqueScorerRefs[si] : 'derived'}>
                      {_.range(NUM_METRICS_IN_SCORER).map(mi => {
                        const dimension = dimensionsForThisScorer[mi];

                        const unit = dimensionUnit(dimension, true);
                        const isBinary = dimension.scoreType === 'binary';
                        const scoreId = dimensionId(dimension);
                        const summaryMetric = adjustValueForDisplay(
                          target.scores[scoreId][currEvalCallId],
                          isBinary
                        );
                        const baseline = adjustValueForDisplay(
                          target.scores[scoreId][leafDims[0]],
                          isBinary
                        );

                        const lowerIsBetter =
                          dimensionShouldMinimize(dimension);
                        return (
                          <React.Fragment key={scoreId}>
                            <GridCell
                              style={{
                                position: 'sticky',
                                left: 0,
                                zIndex: 1,
                                backgroundColor: MOON_100,
                                display: 'flex',
                                flexDirection: 'row',
                                justifyContent: 'space-between  ',
                              }}>
                              <span>
                                {summaryMetric != null ? (
                                  <ValueViewNumber
                                    value={summaryMetric}
                                    fractionDigits={SIGNIFICANT_DIGITS}
                                  />
                                ) : (
                                  <NotApplicable />
                                )}
                                {unit}
                              </span>
                              <ComparisonPill
                                value={summaryMetric}
                                baseline={baseline}
                                metricUnit={unit}
                                metricLowerIsBetter={lowerIsBetter}
                              />
                            </GridCell>
                            {_.range(NUM_TRIALS).map(ti => {
                              const metricValue =
                                trialsForThisEval[ti].scores[scoreId][
                                  currEvalCallId
                                ];
                              if (metricValue == null) {
                                return (
                                  <GridCell key={ti}>
                                    <NotApplicable />
                                  </GridCell>
                                );
                              }

                              return (
                                <GridCell
                                  key={ti}
                                  button={isScorerMetric}
                                  onClick={
                                    isScorerMetric
                                      ? () =>
                                          onScorerClick(
                                            trialsForThisEval[ti]
                                              .predictAndScore.scorerMetrics[
                                              scoreId
                                            ].sourceCall._rawScoreTraceData
                                          )
                                      : undefined
                                  }>
                                  <CellValue value={metricValue} />
                                </GridCell>
                              );
                            })}
                          </React.Fragment>
                        );
                      })}
                    </React.Fragment>
                  );
                })}
              </GridCell>
            );
          })}
        </GridCell>
      </GridContainer>
    </VerticalBox>
  );
};

const removePrefix = (key: string, prefix: string) => {
  if (key.startsWith(prefix)) {
    return key.slice(prefix.length);
  }
  return key;
};

const ICValueView: React.FC<{value: any}> = ({value}) => {
  let text = '';
  if (value == null) {
    return <NotApplicable />;
  } else if (typeof value === 'object') {
    text = JSON.stringify(value || {}, null, 2);
  } else if (typeof value === 'string' && isRef(value)) {
    return <SmallRef objRef={parseRef(value)} />;
  } else {
    text = value.toString();
  }

  text = trimWhitespace(text);

  return (
    <pre
      style={{
        whiteSpace: 'pre-wrap',
        textAlign: 'left',
        wordBreak: 'break-all',
      }}>
      {text}
    </pre>
  );
};
const trimWhitespace = (str: string) => {
  // Trim leading and trailing whitespace
  return str.replace(/^\s+|\s+$/g, '');
};
