import {Box} from '@material-ui/core';
import _ from 'lodash';
import React, {useMemo} from 'react';
import styled from 'styled-components';

import {MOON_100, MOON_300} from '../../../../../../common/css/color.styles';
import {parseRef, WeaveObjectRef} from '../../../../../../react';
import {Button} from '../../../../../Button';
import {CellValue} from '../../../Browse2/CellValue';
import {NotApplicable} from '../../../Browse2/NotApplicable';
import {SmallRef} from '../../../Browse2/SmallRef';
import {isRef} from '../common/util';
import {useCompareEvaluationsState} from './compareEvaluationsContext';
import {removePrefix, useFilteredAggregateRows} from './comparisonTableUtil';
import {EvaluationCallLink} from './EvaluationDefinition';
import {HorizontalBox, VerticalBox} from './Layout';
import {EvaluationComparisonState} from './types';
import {ICValueView} from './InputComparison';
import {SIGNIFICANT_DIGITS} from './constants';
import {Pill, TagColorName} from '../../../../../Tag';
import {ValueViewNumber} from '../CallPage/ValueViewNumber';

const GridCell = styled.div<{cols?: number; rows?: number; noPad?: boolean}>`
  border: 1px solid ${MOON_300};
  grid-column-end: span ${props => props.cols || 1};
  grid-row-end: span ${props => props.rows || 1};
  padding: ${props => (props.noPad ? '0px' : '8px')};
  /* min-width: 100px; */
`;

const GridHeaderCell = styled.div<{cols?: number; rows?: number}>`
  border: 1px solid ${MOON_300};
  background-color: ${MOON_100};
  position: sticky;
  top: 0;
  grid-column-end: span ${props => props.cols || 1};
  grid-row-end: span ${props => props.rows || 1};
  z-index: 1;
`;
const GridContainer = styled.div<{numColumns: number}>`
  display: grid;
  /* grid-template-columns: ${props => '1fr '.repeat(props.numColumns)}; */
  /* grid-gap: 10px; */
`;

const verticalStyle: React.CSSProperties = {
  writingMode: 'vertical-rl',
  transform: 'rotate(180deg)',
};

export const InputComparison2: React.FC<{
  state: EvaluationComparisonState;
}> = props => {
  const {filteredRows, inputColumnKeys, outputColumnKeys, scoreMap, leafDims} =
    useFilteredAggregateRows(props.state);
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

  const inputRef = parseRef(target.inputRef) as WeaveObjectRef;

  //   console.log('target', target);

  const scores = Object.entries(scoreMap).map(v => {
    return {
      scoreId: v[0],
      scorerDim: v[1],
    };
  });
  const sortedScorers = _.sortBy(scores, k => k.scorerDim.scorerRef);
  const uniqueScorerRefs = _.uniq(
    sortedScorers.map(v => v.scorerDim.scorerRef)
  );

  const NUM_SCORERS = uniqueScorerRefs.length;
  const NUM_METRICS = sortedScorers.length;
  const NUM_METRIC_COLS = NUM_METRICS + 1;
  const NUM_COLS =
    1 + // Input / Eval Title
    2 + // Input Prop Key / Val
    NUM_METRIC_COLS;
  const NUM_INPUT_PROPS = inputColumnKeys.length;
  const NUM_OUTPUT_KEYS = outputColumnKeys.length;
  const NUM_EVALS = leafDims.length;
  const FREE_TEXT_COL_NDX = 2;
  const TOTAL_ROWS = NUM_INPUT_PROPS + NUM_OUTPUT_KEYS * NUM_EVALS;

  const [selectedTrials, setSelectedTrials] = React.useState<{
    [evalCallId: string]: number;
  }>({});

  return (
    <VerticalBox
      sx={{
        height: '100%', // 'calc(100vh - 116px)',
        //   bgcolor: 'blue',
        gridGap: '0px',
      }}>
      <HorizontalBox
        sx={{
          //   height: '50px',
          justifyContent: 'space-between',
          alignItems: 'center',
          bgcolor: MOON_100,
          padding: '16px',
        }}>
        {`Viewing Result ${targetIndex + 1} of ${filteredRows.length}`}
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
          height: '100%', // 'calc(100vh - 116px)',
          flex: 1,
          display: 'grid',
          overflow: 'auto',
          gridTemplateColumns: `repeat(2, min-content) auto`,
          //   gridTemplateColumns: `repeat(${FREE_TEXT_COL_NDX}, min-content) 1fr repeat(${
          //     NUM_COLS - FREE_TEXT_COL_NDX - 1
          //   }, min-content`,
          //   gridTemplateRows: `repeat(${NUM_INPUT_PROPS}, min-content) repeat(${TOTAL_ROWS} 1fr) `,
        }}>
        <GridCell rows={NUM_INPUT_PROPS}>Input Ref</GridCell>
        {_.range(NUM_INPUT_PROPS).map(ii => {
          return (
            <React.Fragment>
              <GridCell>{removePrefix(inputColumnKeys[ii], 'input.')}</GridCell>
              <GridCell>
                <ICValueView value={target.input[inputColumnKeys[ii]]} />
              </GridCell>
            </React.Fragment>
          );
        })}
        <GridCell cols={2}></GridCell>
        <GridCell
          noPad
          style={{
            display: 'grid',
            gridTemplateRows: 'subgrid',
            gridTemplateColumns: `repeat(${NUM_EVALS}, min-content auto)`,
            overflowX: 'auto',
          }}
          rows={NUM_OUTPUT_KEYS + 2 + NUM_METRICS}>
          {_.range(NUM_EVALS).map(ei => {
            const currEvalCallId = leafDims[ei];
            return (
              <GridCell cols={2}>
                <EvaluationCallLink
                  callId={currEvalCallId}
                  state={props.state}
                />
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
                <GridCell cols={2}>
                  <ICValueView
                    value={
                      selectedTrial.output[outputColumnKeys[oi]][currEvalCallId]
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
                cols={2}
                rows={NUM_METRICS + 1}
                noPad
                style={{
                  display: 'grid',
                  gridTemplateRows: 'subgrid',
                  gridTemplateColumns: `repeat(${NUM_TRIALS + 1}, auto)`,
                  overflowX: 'auto',
                }}>
                <GridCell
                  style={{
                    position: 'sticky',
                    left: 0,
                    zIndex: 1,
                    backgroundColor: MOON_100,
                  }}>
                  Aggregate Metrics
                </GridCell>
                {_.range(NUM_TRIALS).map(ti => {
                  return (
                    <GridCell
                      style={{
                        textAlign: 'center',
                      }}>
                      <Button
                        size="small"
                        variant={
                          selectedTrialNdx === ti ? 'primary' : 'secondary'
                        }
                        onClick={() => {
                          //   console.log('selecting');
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
                {_.range(NUM_SCORERS).map(si => {
                  const NUM_METRICS_IN_SCORER = 1;
                  return (
                    <React.Fragment>
                      {_.range(NUM_METRICS_IN_SCORER).map(mi => {
                        const isBaseline = ei === 0;
                        const scorersForThisRef = sortedScorers.filter(
                          s => s.scorerDim.scorerRef === uniqueScorerRefs[si]
                        );
                        const summaryMetric =
                          target.scores[scorersForThisRef[mi].scoreId][
                            currEvalCallId
                          ];
                        const unit =
                          scorersForThisRef[mi].scorerDim.scoreType === 'binary'
                            ? '%'
                            : '';
                        let color: TagColorName = 'moon';
                        const baseline =
                          target.scores[scorersForThisRef[mi].scoreId][
                            leafDims[0]
                          ];
                        const diff = summaryMetric - baseline;
                        const lowerIsBetter = false;
                        if (diff > 0) {
                          if (!lowerIsBetter) {
                            color = 'green';
                          } else {
                            color = 'red';
                          }
                        } else if (diff < 0) {
                          if (!lowerIsBetter) {
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
                          <React.Fragment>
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
                              {!isBaseline &&
                                diff !== 0 &&
                                summaryMetric != null &&
                                baseline != null && (
                                  <Pill
                                    label={
                                      (diff > 0 ? '+' : '') + diffFixed + unit
                                    }
                                    color={color}
                                  />
                                )}
                            </GridCell>
                            {_.range(NUM_TRIALS).map(ti => {
                              const metricValue =
                                trialsForThisEval[ti].scores[
                                  scorersForThisRef[mi].scoreId
                                ][currEvalCallId];
                              if (metricValue == null) {
                                return (
                                  <GridCell>
                                    <NotApplicable />
                                  </GridCell>
                                );
                              }

                              return (
                                <GridCell>
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
        {_.range(NUM_OUTPUT_KEYS).map(oi => {
          return (
            <React.Fragment>
              <GridCell></GridCell>
              <GridCell cols={1}>
                {removePrefix(outputColumnKeys[oi], 'output.')}
              </GridCell>
            </React.Fragment>
          );
        })}
        <GridCell cols={2}>Metrics</GridCell>
        {_.range(NUM_SCORERS).map(si => {
          const scorersForThisRef = sortedScorers.filter(
            s => s.scorerDim.scorerRef === uniqueScorerRefs[si]
          );
          const NUM_METRICS_IN_SCORER = scorersForThisRef.length;
          const scorerRef = uniqueScorerRefs[si];
          return (
            <React.Fragment>
              <GridCell rows={NUM_METRICS_IN_SCORER}>
                <SmallRef objRef={parseRef(scorerRef) as WeaveObjectRef} />
              </GridCell>
              {_.range(NUM_METRICS_IN_SCORER).map(mi => {
                return (
                  <React.Fragment>
                    <GridCell>
                      {
                        scorersForThisRef[mi].scorerDim.scoreKeyPath
                          .split('.')
                          .slice(-1)[0]
                      }
                    </GridCell>
                  </React.Fragment>
                );
              })}
            </React.Fragment>
          );
        })}
      </GridContainer>
    </VerticalBox>
  );
};
