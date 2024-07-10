/**
 * TODO:
 * * Audit symbol names
 * The Super challenge header
 * Fixed-Width Sidebar
 */

import {Box} from '@material-ui/core';
import {Circle} from '@mui/icons-material';
import _ from 'lodash';
import React, {useCallback, useEffect, useMemo, useRef} from 'react';
import {useHistory} from 'react-router-dom';
import styled from 'styled-components';

import {
  MOON_100,
  MOON_200,
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

const NEW_FIXED_SIDEBAR_WIDTH_PX = 250;
const NEW_FIXED_MIN_EVAL_WIDTH_PX = 350;
const HEADER_HEIGHT_PX = 38;
const TOP_CELL_PADDING_PX = 4;

const PropKey = styled.div`
  position: sticky;
  top: ${TOP_CELL_PADDING_PX}px;
  overflow: auto;
  text-align: right;
  scrollbar-width: none;
`;

const GridCell = styled.div<{
  colSpan?: number;
  rowSpan?: number;
  button?: boolean;
}>`
  border: 1px solid ${MOON_200};
  grid-column-end: span ${props => props.colSpan || 1};
  grid-row-end: span ${props => props.rowSpan || 1};
  padding: ${TOP_CELL_PADDING_PX}px 8px;
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

const CENTERED_TEXT: React.CSSProperties = {
  display: 'flex',
  justifyContent: 'center',
  alignItems: 'center',
  textAlign: 'center',
};

const STICKY_HEADER: React.CSSProperties = {
  ...CENTERED_TEXT,
  position: 'sticky',
  top: 0,
  zIndex: 1,
  backgroundColor: MOON_100,
  fontWeight: 'bold',
};

const STICKY_SIDEBAR: React.CSSProperties = {
  position: 'sticky',
  left: 0,
  zIndex: 1,
  backgroundColor: MOON_100,
  fontWeight: 'bold',
};

const STICKY_SIDEBAR_HEADER: React.CSSProperties = {
  ...STICKY_HEADER,
  ...STICKY_SIDEBAR,
  zIndex: 2,
};

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
  // const NUM_METRICS = NUM_DERIVED + Object.values(props.state.data.scorerMetricDimensions).length;
  // const NUM_COLS =
  //   1 + // Input / Eval Title
  //   2; // Input Prop Key / Val

  // const NUM_INPUT_PROPS = inputColumnKeys.length;
  // const NUM_OUTPUT_KEYS = outputColumnKeys.length;
  // const NUM_EVALS = leafDims.length;

  const header = (
    <HorizontalBox
      sx={{
        justifyContent: 'space-between',
        alignItems: 'center',
        bgcolor: MOON_100,
        padding: '16px',
        borderBottom: '1px solid #ccc',
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

  const inputColumnKeys = Object.keys(target.input);
  const SHOW_INPUT_HEADER = true;
  const NEW_NUM_INPUT_PROPS = inputColumnKeys.length;
  const NEW_NUM_OUTPUT_KEYS = outputColumnKeys.length;
  const NUM_DERIVED = derivedScorers.length;
  const NEW_NUM_METRICS_PER_SCORER = [
    ...uniqueScorerRefs.map(scorer => {
      return sortedScorers.filter(s => s.scorerDef.scorerOpOrObjRef === scorer)
        .length;
    }),
    NUM_DERIVED,
  ];
  const NEW_TOTAL_METRICS = _.sum(NEW_NUM_METRICS_PER_SCORER);
  // const NEW_NUM_SCORERS = NEW_NUM_METRICS_PER_SCORER.length;
  const NEW_NUM_TRIALS = leafDims.map(leafId => {
    return target.originalRows.filter(row => row.evaluationCallId === leafId)
      .length;
  });
  const NEW_NUM_EVALS = NEW_NUM_TRIALS.length;

  const compKeyForInputPropIndex = (inputPropIndex: number) => {
    return inputColumnKeys[inputPropIndex];
  };

  const keyForEvalIndex = (evalIndex: number) => {
    return leafDims[evalIndex];
  };

  const inputPropKeyCompForInputPropIndex = (inputPropIndex: number) => {
    // (SHOW_INPUT_HEADER ? 1 : 0)
    return (
      <PropKey
        style={{
          top:
            TOP_CELL_PADDING_PX +
            (SHOW_INPUT_HEADER ? 1 + HEADER_HEIGHT_PX : 0),
        }}>
        {removePrefix(compKeyForInputPropIndex(inputPropIndex), 'input.')}
      </PropKey>
    );
  };

  const inputPropValCompForInputPropIndex = (inputPropIndex: number) => {
    return (
      <ICValueView
        value={target.input[compKeyForInputPropIndex(inputPropIndex)]}
      />
    );
  };

  const predictCallCompForEvaluationIndex = (evalIndex: number) => {
    const currEvalCallId = leafDims[evalIndex];
    const trialsForThisEval = target.originalRows.filter(
      row => row.evaluationCallId === currEvalCallId
    );
    const selectedTrial =
      trialsForThisEval[selectedTrials[currEvalCallId] || 0];
    const trialPredict = selectedTrial.predictAndScore._rawPredictTraceData;
    const [trialEntity, trialProject] =
      trialPredict?.project_id.split('/') ?? [];
    const trialOpName = parseRefMaybe(
      trialPredict?.op_name ?? ''
    )?.artifactName;
    const trialCallId = trialPredict?.id;
    const evaluationCall = props.state.data.evaluationCalls[currEvalCallId];
    if (trialEntity && trialProject && trialOpName && trialCallId) {
      return (
        <Box
          style={{
            overflow: 'hidden',
          }}>
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
        </Box>
      );
    }
    return null;
  };

  const compKeyCompForOutputPropIndex = (outputPropIndex: number) => {
    return outputColumnKeys[outputPropIndex];
  };

  const outputKeyCompForOutputPropIndex = (outputPropIndex: number) => {
    return (
      <PropKey
        style={{
          top: TOP_CELL_PADDING_PX + 1 + HEADER_HEIGHT_PX,
        }}>
        {removePrefix(
          compKeyCompForOutputPropIndex(outputPropIndex),
          'output.'
        )}
      </PropKey>
    );
  };

  const outputValueCompForOutputPropIndex = (
    evaluationIndex: number,
    outputPropIndex: number
  ) => {
    const currEvalCallId = leafDims[evaluationIndex];
    const trialsForThisEval = target.originalRows.filter(
      row => row.evaluationCallId === currEvalCallId
    );

    const selectedTrial =
      trialsForThisEval[selectedTrials[currEvalCallId] || 0];

    return (
      <ICValueView
        value={
          (selectedTrial?.output?.[outputColumnKeys[outputPropIndex]] ?? {})[
            currEvalCallId
          ]
        }
      />
    );
  };

  const trialCompForEvaluationIndex = (
    evalIndex: number,
    trialIndex: number
  ) => {
    const currEvalCallId = leafDims[evalIndex];
    const selectedTrialNdx = selectedTrials[currEvalCallId] || 0;
    return (
      <Button
        size="small"
        variant={selectedTrialNdx === trialIndex ? 'primary' : 'secondary'}
        onClick={() => {
          setSelectedTrials(curr => {
            return {
              ...curr,
              [currEvalCallId]: trialIndex,
            };
          });
        }}
        icon="show-visible">
        {trialIndex.toString()}
      </Button>
    );
  };

  const scorerCompForScorerIndex = (scorerIndex: number) => {
    if (scorerIndex === NUM_SCORERS) {
      return null; // derived
    }
    const scorerRef = uniqueScorerRefs[scorerIndex];
    return (
      <VerticalBox
        style={{
          alignItems: 'center',
          justifyContent: 'center',
          width: '100%',
          height: '100%',
          paddingLeft: '2px',
        }}>
        <SmallRef objRef={parseRef(scorerRef) as WeaveObjectRef} iconOnly />
      </VerticalBox>
    );
  };

  const metricCompForScorerIndex = (
    scorerIndex: number,
    metricIndex: number
  ) => {
    const isDerivedMetric = scorerIndex === NUM_SCORERS;
    const dimensionsForThisScorer = isDerivedMetric
      ? derivedScorers
      : sortedScorers.filter(
          s => s.scorerDef.scorerOpOrObjRef === uniqueScorerRefs[scorerIndex]
        );
    return (
      <PropKey>{dimensionLabel(dimensionsForThisScorer[metricIndex])}</PropKey>
    );
  };

  const aggregateMetricCompForScorerIndex = (
    scorerIndex: number,
    metricIndex: number,
    evalIndex: number
  ) => {
    const isDerivedMetric = scorerIndex === NUM_SCORERS;
    const currEvalCallId = leafDims[evalIndex];
    const dimensionsForThisScorer = isDerivedMetric
      ? derivedScorers
      : sortedScorers.filter(
          s => s.scorerDef.scorerOpOrObjRef === uniqueScorerRefs[scorerIndex]
        );
    const dimension = dimensionsForThisScorer[metricIndex];

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

    const lowerIsBetter = dimensionShouldMinimize(dimension);

    if (summaryMetric == null) {
      return <NotApplicable />;
    }

    return (
      <HorizontalBox
        style={{
          alignItems: 'center',
          justifyContent: 'space-between',
        }}>
        <HorizontalBox
          style={{
            alignItems: 'center',
            gap: '1px',
          }}>
          <ValueViewNumber
            fractionDigits={SIGNIFICANT_DIGITS}
            value={summaryMetric}
          />
          {unit}
        </HorizontalBox>
        <ComparisonPill
          value={summaryMetric}
          baseline={baseline}
          metricUnit={unit}
          metricLowerIsBetter={lowerIsBetter}
        />
      </HorizontalBox>
    );
  };

  const trialMetricCompForScorerIndex = (
    scorerIndex: number,
    metricIndex: number,
    evalIndex: number,
    trialIndex: number
  ) => {
    const isDerivedMetric = scorerIndex === NUM_SCORERS;
    const currEvalCallId = leafDims[evalIndex];
    const dimensionsForThisScorer = isDerivedMetric
      ? derivedScorers
      : sortedScorers.filter(
          s => s.scorerDef.scorerOpOrObjRef === uniqueScorerRefs[scorerIndex]
        );
    const dimension = dimensionsForThisScorer[metricIndex];
    const scoreId = dimensionId(dimension);
    const trialsForThisEval = target.originalRows.filter(
      row => row.evaluationCallId === currEvalCallId
    );
    const metricValue =
      trialsForThisEval[trialIndex].scores[scoreId][currEvalCallId];
    if (metricValue == null) {
      return <NotApplicable />;
    }

    return <CellValue value={metricValue} />;
  };

  const trialMetricOnClickForScorerIndex = (
    scorerIndex: number,
    metricIndex: number,
    evalIndex: number,
    trialIndex: number
  ) => {
    const isDerivedMetric = scorerIndex === NUM_SCORERS;
    const currEvalCallId = leafDims[evalIndex];
    const dimensionsForThisScorer = isDerivedMetric
      ? derivedScorers
      : sortedScorers.filter(
          s => s.scorerDef.scorerOpOrObjRef === uniqueScorerRefs[scorerIndex]
        );
    const dimension = dimensionsForThisScorer[metricIndex];
    const scoreId = dimensionId(dimension);
    const trialsForThisEval = target.originalRows.filter(
      row => row.evaluationCallId === currEvalCallId
    );

    if (isDerivedMetric) {
      return undefined;
    }
    return () =>
      onScorerClick(
        trialsForThisEval[trialIndex].predictAndScore.scorerMetrics[scoreId]
          .sourceCall._rawScoreTraceData
      );
  };

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
          }, auto)`}
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
              <React.Fragment key={compKeyForInputPropIndex(inputPropIndex)}>
                <GridCell style={{...STICKY_SIDEBAR}}>
                  {inputPropKeyCompForInputPropIndex(inputPropIndex)}
                </GridCell>
                <GridCell>
                  {inputPropValCompForInputPropIndex(inputPropIndex)}
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
          rowsTemp={`${HEADER_HEIGHT_PX}px repeat(${NEW_NUM_OUTPUT_KEYS}, auto)`}
          colsTemp={`${NEW_FIXED_SIDEBAR_WIDTH_PX}px repeat(${NEW_NUM_EVALS}, minmax(${NEW_FIXED_MIN_EVAL_WIDTH_PX}px, 1fr))`}
          style={{
            scrollbarWidth: 'none',
          }}>
          {/* OUTPUT HEADER */}
          <React.Fragment>
            <GridCell style={{...STICKY_SIDEBAR_HEADER}}>
              Model Outputs
            </GridCell>
            {_.range(NEW_NUM_EVALS).map(evalIndex => {
              return (
                <GridCell
                  key={keyForEvalIndex(evalIndex)}
                  style={{...STICKY_HEADER}}>
                  {predictCallCompForEvaluationIndex(evalIndex)}
                </GridCell>
              );
            })}
          </React.Fragment>
          {/* OUTPUT ROWS */}
          {_.range(NEW_NUM_OUTPUT_KEYS).map(outputPropIndex => {
            return (
              <React.Fragment
                key={compKeyCompForOutputPropIndex(outputPropIndex)}>
                <GridCell style={{...STICKY_SIDEBAR}}>
                  {outputKeyCompForOutputPropIndex(outputPropIndex)}
                </GridCell>
                {_.range(NEW_NUM_EVALS).map(evalIndex => {
                  return (
                    <GridCell key={keyForEvalIndex(evalIndex)}>
                      {outputValueCompForOutputPropIndex(
                        evalIndex,
                        outputPropIndex
                      )}
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
          rowsTemp={`${HEADER_HEIGHT_PX}px repeat(${NEW_TOTAL_METRICS}, auto)`}
          colsTemp={`${NEW_FIXED_SIDEBAR_WIDTH_PX}px repeat(${NEW_NUM_EVALS}, minmax(${NEW_FIXED_MIN_EVAL_WIDTH_PX}px, 1fr))`}>
          {/* METRIC HEADER */}
          <React.Fragment>
            <GridCell
              style={{
                // in a perfect world, this would be STICKY_SIDEBAR_HEADER,
                // but I can't get the eval metric headers to be sticky. I
                // have spent many hours trying to pull this one off and need
                // to move on. The result is that the metrics headers (and trial selection
                // buttons) will scroll off the screen. Not horrible, but a defeat.
                ...STICKY_SIDEBAR,
                ...CENTERED_TEXT,
                zIndex: 3,
              }}>
              Metrics
            </GridCell>
            {_.range(NEW_NUM_EVALS).map(evalIndex => {
              const TRIALS_FOR_EVAL = NEW_NUM_TRIALS[evalIndex];
              return (
                <GridCellSubgrid
                  key={keyForEvalIndex(evalIndex)}
                  rowSpan={NEW_TOTAL_METRICS + 1}
                  colSpan={1}
                  colsTemp={`min-content repeat(${TRIALS_FOR_EVAL} , auto)`}>
                  <GridCell style={{...STICKY_SIDEBAR_HEADER}}>Trials</GridCell>
                  {_.range(TRIALS_FOR_EVAL).map(trialIndex => {
                    return (
                      <GridCell key={trialIndex} style={{...STICKY_HEADER}}>
                        {trialCompForEvaluationIndex(evalIndex, trialIndex)}
                      </GridCell>
                    );
                  })}
                  {NEW_NUM_METRICS_PER_SCORER.map((numMetrics, scorerIndex) => {
                    return _.range(numMetrics).map(metricIndex => {
                      return (
                        <React.Fragment
                          key={
                            scorerIndex.toString() +
                            '.' +
                            metricIndex.toString()
                          }>
                          <GridCell style={{...STICKY_SIDEBAR}}>
                            {aggregateMetricCompForScorerIndex(
                              scorerIndex,
                              metricIndex,
                              evalIndex
                            )}
                          </GridCell>
                          {_.range(TRIALS_FOR_EVAL).map(trialIndex => {
                            const onClick = trialMetricOnClickForScorerIndex(
                              scorerIndex,
                              metricIndex,
                              evalIndex,
                              trialIndex
                            );

                            return (
                              <GridCell
                                key={trialIndex}
                                button={onClick != null}
                                onClick={onClick}>
                                {trialMetricCompForScorerIndex(
                                  scorerIndex,
                                  metricIndex,
                                  evalIndex,
                                  trialIndex
                                )}
                              </GridCell>
                            );
                          })}
                        </React.Fragment>
                      );
                    });
                  })}
                </GridCellSubgrid>
              );
            })}
          </React.Fragment>
          {/* METRIC ROWS */}
          <GridCellSubgrid
            rowSpan={NEW_TOTAL_METRICS}
            colSpan={1}
            colsTemp={`45px ${NEW_FIXED_SIDEBAR_WIDTH_PX - 45}px`}
            style={{...STICKY_SIDEBAR}}>
            {NEW_NUM_METRICS_PER_SCORER.map(
              (NUM_METRICS_FOR_SCORER, scorerIndex) => {
                return (
                  <React.Fragment key={scorerIndex}>
                    <GridCell
                      style={{...STICKY_SIDEBAR}}
                      rowSpan={NUM_METRICS_FOR_SCORER}>
                      {scorerCompForScorerIndex(scorerIndex)}
                    </GridCell>
                    {_.range(NUM_METRICS_FOR_SCORER).map(metricIndex => {
                      return (
                        <GridCell
                          key={metricIndex}
                          style={{
                            backgroundColor: MOON_100,
                          }}>
                          {metricCompForScorerIndex(scorerIndex, metricIndex)}
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
