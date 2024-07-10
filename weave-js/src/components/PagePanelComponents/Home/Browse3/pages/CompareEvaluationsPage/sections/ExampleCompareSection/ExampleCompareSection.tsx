import {Box} from '@material-ui/core';
import {Circle} from '@mui/icons-material';
import _ from 'lodash';
import React, {useCallback, useEffect, useMemo, useRef} from 'react';
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
  colSpan?: number;
  rowSpan?: number;
  button?: boolean;
}>`
  border: 1px solid ${MOON_300};
  grid-column-end: span ${props => props.colSpan || 1};
  grid-row-end: span ${props => props.rowSpan || 1};
  padding: 8px;
  background-color: white;
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

const GridCellSubgrid = styled.div<{
  colSpan?: number;
  rowSpan?: number;
  colsTemp?: string;
  rowsTemp?: string;
}>`
  grid-column-end: span ${props => props.colSpan || 1};
  grid-row-end: span ${props => props.rowSpan || 1};
  padding: 0px;
  background-color: white;
  display: grid;
  grid-template-rows: ${props => props.rowsTemp || 'subgrid'};
  grid-template-columns: ${props => props.colsTemp || 'subgrid'};
  overflow: auto;
`;

const GridContainer = styled.div<{colsTemp: string; rowsTemp: string}>`
  display: grid;
  overflow: auto;
  grid-template-columns: ${props => props.colsTemp};
  grid-template-rows: ${props => props.rowsTemp};
`;

const STICKY_HEADER: React.CSSProperties = {
  position: 'sticky',
  top: 0,
  zIndex: 1,
  backgroundColor: MOON_100,
};

const STICKY_SIDEBAR: React.CSSProperties = {
  position: 'sticky',
  left: 0,
  zIndex: 1,
  backgroundColor: MOON_100,
};

const STICKY_SIDEBAR_HEADER: React.CSSProperties = {
  ...STICKY_HEADER,
  ...STICKY_SIDEBAR,
  zIndex: 2,
};

const LOREM_IPSUM = `Lorem ipsum dolor sit amet, consectetur adipiscing elit. Sed non risus. Suspendisse lectus tortor, dignissim sit amet, adipiscing nec, ultricies sed, dolor. Cras elementum ultrices diam. Maecenas ligula massa, varius a, semper congue, euismod non, mi.`;

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

  const {ref1, ref2} = useLinkHorizontalScroll();

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

  const header = (
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
  );

  const SHOW_INPUT_HEADER = true;
  const NEW_NUM_INPUT_PROPS = 10;
  const NEW_NUM_OUTPUT_KEYS = 2;
  const NEW_NUM_METRICS_PER_SCORER = [1, 2, 3, 4];
  const NEW_TOTAL_METRICS = _.sum(NEW_NUM_METRICS_PER_SCORER);
  const NEW_NUM_SCORERS = NEW_NUM_METRICS_PER_SCORER.length;
  const NEW_NUM_TRIALS = [1, 2, 3, 4];
  const NEW_NUM_EVALS = NEW_NUM_TRIALS.length;
  const NEW_FIXED_SIDEBAR_WIDTH_PX = 250;
  const NEW_FIXED_MIN_EVAL_WIDTH_PX = 350;

  return (
    <VerticalBox
      sx={{
        height: '100%',
        gridGap: '0px',
      }}>
      {header}
      <GridContainer
        colsTemp={'auto'}
        rowsTemp={`fit-content(100%) auto fit-content(100%)`}
        style={{
          height: '100%',
          flex: 1,
        }}>
        {/* INPUT SECTION */}
        <GridCellSubgrid
          rowSpan={1}
          colSpan={1}
          rowsTemp={`repeat(${
            NEW_NUM_INPUT_PROPS + (SHOW_INPUT_HEADER ? 1 : 0)
          })`}
          colsTemp={`${NEW_FIXED_SIDEBAR_WIDTH_PX}px auto`}>
          {/* INPUT HEADER */}
          {SHOW_INPUT_HEADER && (
            <React.Fragment>
              <GridCell style={{...STICKY_SIDEBAR_HEADER}}>Input</GridCell>
              <GridCell style={{...STICKY_HEADER}}>Value</GridCell>
            </React.Fragment>
          )}
          {/* INPUT ROWS */}
          {_.range(NEW_NUM_INPUT_PROPS).map(inputPropIndex => {
            return (
              <React.Fragment key={inputPropIndex}>
                <GridCell style={{...STICKY_SIDEBAR}}>
                  IK_{inputPropIndex}
                </GridCell>
                <GridCell>
                  IV_{inputPropIndex}: {LOREM_IPSUM}
                </GridCell>
              </React.Fragment>
            );
          })}
        </GridCellSubgrid>
        {/* OUTPUT SECTION */}
        <GridCellSubgrid
          ref={ref1}
          rowSpan={1}
          colSpan={1}
          rowsTemp={`min-content repeat(${NEW_NUM_OUTPUT_KEYS}, auto)`}
          colsTemp={`${NEW_FIXED_SIDEBAR_WIDTH_PX}px repeat(${NEW_NUM_EVALS}, minmax(${NEW_FIXED_MIN_EVAL_WIDTH_PX}px, 1fr))`}
          style={{
            scrollbarWidth: 'none',
          }}>
          {/* OUTPUT HEADER */}
          <React.Fragment>
            <GridCell style={{...STICKY_SIDEBAR_HEADER}}>Outputs</GridCell>
            {_.range(NEW_NUM_EVALS).map(evalIndex => {
              return (
                <GridCell style={{...STICKY_HEADER}}>Eval {evalIndex}</GridCell>
              );
            })}
          </React.Fragment>
          {/* OUTPUT ROWS */}
          {_.range(NEW_NUM_OUTPUT_KEYS).map(outputPropIndex => {
            return (
              <React.Fragment key={outputPropIndex}>
                <GridCell style={{...STICKY_SIDEBAR}}>
                  OK_{outputPropIndex}
                </GridCell>
                {_.range(NEW_NUM_EVALS).map(evalIndex => {
                  return (
                    <GridCell>
                      E_{evalIndex}_OK_{outputPropIndex}: {LOREM_IPSUM}{' '}
                      {LOREM_IPSUM}
                    </GridCell>
                  );
                })}
              </React.Fragment>
            );
          })}
        </GridCellSubgrid>
        {/* METRIC SECTION */}
        <GridCellSubgrid
          ref={ref2}
          rowSpan={1}
          colSpan={1}
          rowsTemp={`repeat(${NEW_TOTAL_METRICS + 1})`}
          colsTemp={`${NEW_FIXED_SIDEBAR_WIDTH_PX}px repeat(${NEW_NUM_EVALS}, minmax(${NEW_FIXED_MIN_EVAL_WIDTH_PX}px, 1fr))`}>
          {/* METRIC HEADER */}
          <React.Fragment>
            <GridCell style={{...STICKY_SIDEBAR_HEADER, zIndex: 3}}>
              Metrics
            </GridCell>
            {_.range(NEW_NUM_EVALS).map(evalIndex => {
              const TRIALS_FOR_EVAL = NEW_NUM_TRIALS[evalIndex];
              return (
                <GridCellSubgrid
                  style={{}}
                  rowSpan={NEW_TOTAL_METRICS + 1}
                  colSpan={1}
                  colsTemp={`min-content repeat(${TRIALS_FOR_EVAL} , auto)`}>
                  <GridCell style={{...STICKY_SIDEBAR_HEADER}}>
                    E_{evalIndex}_AGG
                  </GridCell>
                  {_.range(TRIALS_FOR_EVAL).map(trialIndex => {
                    return (
                      <GridCell style={{...STICKY_HEADER}}>
                        T_{trialIndex}
                      </GridCell>
                    );
                  })}
                  {_.range(NEW_TOTAL_METRICS).map(scorerIndex => {
                    return (
                      <React.Fragment key={scorerIndex}>
                        <GridCell style={{...STICKY_SIDEBAR}}>
                          SM_{scorerIndex}
                        </GridCell>
                        {_.range(TRIALS_FOR_EVAL).map(trialIndex => {
                          return (
                            <GridCell>
                              SM_{scorerIndex}_E_{evalIndex}_T_{trialIndex}
                            </GridCell>
                          );
                        })}
                      </React.Fragment>
                    );
                  })}
                </GridCellSubgrid>
              );
            })}
          </React.Fragment>
          {/* METRIC ROWS */}
          <GridCellSubgrid
            rowSpan={NEW_TOTAL_METRICS}
            colSpan={1}
            colsTemp={`min-content auto`}>
            {NEW_NUM_METRICS_PER_SCORER.map(
              (NUM_METRICS_FOR_SCORER, scorerIndex) => {
                return (
                  <React.Fragment key={scorerIndex}>
                    <GridCell
                      style={{...STICKY_SIDEBAR}}
                      rowSpan={NUM_METRICS_FOR_SCORER}>
                      S_{scorerIndex}
                    </GridCell>
                    {_.range(NUM_METRICS_FOR_SCORER).map(metricIndex => {
                      return (
                        <GridCell style={{...STICKY_SIDEBAR}}>
                          S_{scorerIndex}_MK_{metricIndex}
                        </GridCell>
                      );
                    })}
                  </React.Fragment>
                );
              }
            )}
          </GridCellSubgrid>
        </GridCellSubgrid>
      </GridContainer>
      {/* <GridContainer
        style={{
          height: '100%',
          flex: 1,
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
        <GridCellSubgrid
          cols={2}
          rows={1 + NUM_OUTPUT_KEYS + 1 + NUM_METRICS}
          style={{
            position: 'sticky',
            left: 0,
            zIndex: 3,
            backgroundColor: 'white',
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
          <GridCellSubgrid
            cols={2}
            rows={NUM_METRICS + 1}
            style={{
              position: 'sticky',
              bottom: 0,
              left: 0,
              zIndex: 3,
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
          </GridCellSubgrid>
        </GridCellSubgrid>
        <GridCellSubgrid
          style={{
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
              <GridCellSubgrid
                key={currEvalCallId}
                cols={2}
                rows={NUM_METRICS + 1}
                style={{
                  gridTemplateColumns: `repeat(${NUM_TRIALS + 1}, auto)`,
                  overflowX: 'auto',
                  position: 'sticky',
                  bottom: 0,
                  zIndex: 1,
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
              </GridCellSubgrid>
            );
          })}
        </GridCellSubgrid>
      </GridContainer> */}
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
        padding: 0,
        margin: 0,
      }}>
      {text}
    </pre>
  );
};
const trimWhitespace = (str: string) => {
  // Trim leading and trailing whitespace
  return str.replace(/^\s+|\s+$/g, '');
};

/**
 * Allows 2 divs to scroll horizontally in sync. The user
 * should be able to scroll either div and the other should
 * scroll as well.
 */
const useLinkHorizontalScroll = () => {
  const ref1 = useRef<HTMLDivElement>(null);
  const ref2 = useRef<HTMLDivElement>(null);

  const scroll1Handler = useCallback(() => {
    if (ref1.current && ref2.current) {
      ref2.current.scrollLeft = ref1.current.scrollLeft;
    }
  }, []);

  const scroll2Handler = useCallback(() => {
    if (ref1.current && ref2.current) {
      ref1.current.scrollLeft = ref2.current.scrollLeft;
    }
  }, []);

  useEffect(() => {
    const ref1Current = ref1.current;
    const ref2Current = ref2.current;

    if (ref1Current) {
      ref1Current.addEventListener('scroll', scroll1Handler);
    }

    if (ref2Current) {
      ref2Current.addEventListener('scroll', scroll2Handler);
    }

    return () => {
      if (ref1Current) {
        ref1Current.removeEventListener('scroll', scroll1Handler);
      }
      if (ref2Current) {
        ref2Current.removeEventListener('scroll', scroll2Handler);
      }
    };
  }, [scroll1Handler, scroll2Handler]);

  return {ref1, ref2};
};
