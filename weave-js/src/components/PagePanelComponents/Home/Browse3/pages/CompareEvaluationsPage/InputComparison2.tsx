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
          gridTemplateColumns: `repeat(${FREE_TEXT_COL_NDX}, min-content) 1fr repeat(${
            NUM_COLS - FREE_TEXT_COL_NDX - 1
          }, min-content`,
          gridTemplateRows: `repeat(${NUM_INPUT_PROPS}, min-content) repeat(${TOTAL_ROWS} 1fr) `,
          flex: 1,
          display: 'grid',
          overflow: 'auto',
        }}>
        <GridCell rows={NUM_INPUT_PROPS} style={{...verticalStyle}}>
          <SmallRef objRef={inputRef} iconOnly />
        </GridCell>
        {_.range(NUM_INPUT_PROPS).map(i => {
          return (
            <React.Fragment key={inputColumnKeys[i]}>
              <GridCell>{removePrefix(inputColumnKeys[i], 'input.')}</GridCell>
              <GridCell>
                {/* <CellValue value={target.input[inputColumnKeys[i]]} /> */}
                <ICValueView value={target.input[inputColumnKeys[i]]} />
              </GridCell>
              {i === 0 && (
                <GridCell
                  cols={NUM_METRIC_COLS}
                  rows={NUM_INPUT_PROPS}
                  noPad
                  style={{
                    display: 'grid',
                    gridTemplateColumns: 'subgrid',
                  }}>
                  <GridCell
                    rows={2}
                    style={{
                      ...verticalStyle,
                      backgroundColor: MOON_100,
                    }}>
                    Trials
                  </GridCell>
                  {_.range(NUM_SCORERS).map(si => {
                    const scorerRef = uniqueScorerRefs[si];
                    const numMetrics = sortedScorers.filter(
                      k => k.scorerDim.scorerRef === scorerRef
                    ).length;
                    return (
                      <>
                        <GridCell
                          cols={numMetrics}
                          style={{
                            //   ...verticalStyle,
                            backgroundColor: MOON_100,
                          }}>
                          <SmallRef
                            objRef={parseRef(scorerRef) as WeaveObjectRef}
                            iconOnly
                          />
                        </GridCell>
                      </>
                    );
                  })}
                  {_.range(NUM_METRICS).map(mi => {
                    return (
                      <GridCell
                        style={{
                          ...verticalStyle,
                          backgroundColor: MOON_100,
                        }}>
                        {sortedScorers[mi].scorerDim.scoreKeyPath}
                      </GridCell>
                    );
                  })}
                </GridCell>
              )}
            </React.Fragment>
          );
        })}
        {_.range(NUM_EVALS).map(ei => {
          const currEvalCallId = leafDims[ei];
          const isBaseline = ei === 0;
          const trialsForThisEval = target.originalRows.filter(
            row => row.evaluationCallId === currEvalCallId
          );
          const NUM_TRIALS = trialsForThisEval.length;
          //   console.log({selectedTrials});
          const selectedTrial =
            trialsForThisEval[selectedTrials[currEvalCallId] || 0];
          //   console.log(selectedTrials[currEvalCallId], {selectedTrial});
          // console.log(
          //   trialsForThisEval,
          //   currEvalCallId,
          //   sortedScorers[0][0],
          //   trialsForThisEval[i].scores[sortedScorers[i][0]]
          // );
          return (
            <>
              {/* <GridCell cols={NUM_COLS}>Eval Title {ei}</GridCell> */}
              <GridCell
                rows={NUM_OUTPUT_KEYS}
                style={{
                  ...verticalStyle,
                }}>
                <EvaluationCallLink
                  callId={currEvalCallId}
                  state={props.state}
                />
              </GridCell>
              {_.range(NUM_OUTPUT_KEYS).map(oi => {
                return (
                  <>
                    <GridCell>
                      {removePrefix(outputColumnKeys[oi], 'output.')}
                    </GridCell>
                    <GridCell>
                      {/* <CellValue
                            value={
                              selectedTrial.output[outputColumnKeys[oi]][
                                currEvalCallId
                              ]
                            }
                          /> */}
                      <ICValueView
                        value={
                          selectedTrial.output[outputColumnKeys[oi]][
                            currEvalCallId
                          ]
                        }
                      />
                    </GridCell>
                    {oi === 0 && (
                      <GridCell
                        rows={NUM_OUTPUT_KEYS}
                        cols={NUM_METRIC_COLS}
                        noPad
                        style={{
                          display: 'grid',
                          gridTemplateColumns: 'subgrid',
                          // maxHeight: '300px',
                          overflow: 'auto',
                          gridTemplateRows: `repeat(${
                            NUM_TRIALS + 1
                          }, min-content)`,
                        }}>
                        <GridHeaderCell></GridHeaderCell>
                        {_.range(NUM_METRICS).map(mi => {
                          const summaryMetric =
                            target.scores[sortedScorers[mi].scoreId][
                              currEvalCallId
                            ];
                          // console.log(summaryMetric, sortedScorers[mi]);
                          return (
                            <GridHeaderCell>
                              {summaryMetric}
                              {sortedScorers[mi].scorerDim.scoreType ===
                              'binary'
                                ? '%'
                                : ''}
                              {!isBaseline ? '+/-123' : ''}
                            </GridHeaderCell>
                          );
                        })}
                        {_.range(NUM_TRIALS).map(ti => {
                          return (
                            <>
                              <GridCell
                                onClick={() => {
                                  //   console.log('selecting');
                                  setSelectedTrials(curr => {
                                    return {
                                      ...curr,
                                      [currEvalCallId]: ti,
                                    };
                                  });
                                }}>
                                {ti}
                              </GridCell>
                              {_.range(NUM_METRICS).map(mi => {
                                const metricValue =
                                  trialsForThisEval[ti].scores[
                                    sortedScorers[mi].scoreId
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
                            </>
                          );
                        })}
                      </GridCell>
                    )}
                  </>
                );
              })}
            </>
          );
        })}
      </GridContainer>
    </VerticalBox>
  );
};
