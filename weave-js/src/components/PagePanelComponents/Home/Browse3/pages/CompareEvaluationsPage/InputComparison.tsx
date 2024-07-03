import _ from 'lodash';
import React from 'react';
import styled from 'styled-components';

import {parseRef, WeaveObjectRef} from '../../../../../../react';
import {SmallRef} from '../../../Browse2/SmallRef';
import {removePrefix, useFilteredAggregateRows} from './comparisonTableUtil';
import {HorizontalBox, VerticalBox} from './Layout';
import {EvaluationComparisonState} from './types';
import {EvaluationCallLink} from './EvaluationDefinition';
import {ValueViewNumber} from '../CallPage/ValueViewNumber';
import {CellValue} from '../../../Browse2/CellValue';
import {NotApplicable} from '../../../Browse2/NotApplicable';
import {isRef} from '../common/util';

const GridCell = styled.div<{cols?: number; rows?: number}>`
  border: 1px solid black;
  grid-column-end: span ${props => props.cols || 1};
  grid-row-end: span ${props => props.rows || 1};
  /* min-width: 100px; */
`;

const GridHeaderCell = styled.div<{cols?: number; rows?: number}>`
  border: 1px solid black;
  background-color: lightgray;
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

export const InputComparison: React.FC<{
  state: EvaluationComparisonState;
}> = props => {
  const {filteredRows, inputColumnKeys, outputColumnKeys, scoreMap, leafDims} =
    useFilteredAggregateRows(props.state);

  const target = Object.values(filteredRows)[0];
  const inputRef = parseRef(target.inputRef) as WeaveObjectRef;

  console.log('target', target);

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
    <VerticalBox>
      <HorizontalBox
        sx={{
          height: 'calc(100vh - 116px)',
          //   bgcolor: 'blue',
        }}>
        <GridContainer
          numColumns={NUM_COLS}
          style={{
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
                <GridCell>
                  {removePrefix(inputColumnKeys[i], 'input.')}
                </GridCell>
                <GridCell>
                  {/* <CellValue value={target.input[inputColumnKeys[i]]} /> */}
                  <ValueView value={target.input[inputColumnKeys[i]]} />
                </GridCell>
                {i === 0 && (
                  <GridCell
                    cols={NUM_METRIC_COLS}
                    rows={NUM_INPUT_PROPS}
                    style={{
                      display: 'grid',
                      gridTemplateColumns: 'subgrid',
                    }}>
                    <GridCell
                      rows={2}
                      style={{
                        ...verticalStyle,
                        backgroundColor: 'lightgray',
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
                              backgroundColor: 'lightgray',
                            }}>
                            <SmallRef
                              objRef={parseRef(scorerRef) as WeaveObjectRef}
                              iconOnly
                            />
                          </GridCell>
                        </>
                      );
                    })}
                    {_.range(NUM_METRICS).map(i => {
                      return (
                        <GridCell
                          style={{
                            ...verticalStyle,
                            backgroundColor: 'lightgray',
                          }}>
                          {sortedScorers[i].scorerDim.scoreKeyPath}
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
            const selectedTrial =
              trialsForThisEval[selectedTrials[currEvalCallId] || 0];
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
                        <ValueView
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
                          style={{
                            display: 'grid',
                            gridTemplateColumns: 'subgrid',
                            // maxHeight: '300px',
                            overflow: 'auto',
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
                                <GridCell>{ti}</GridCell>
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
      </HorizontalBox>
    </VerticalBox>
  );
};

// {_.range(NUM_COLS - NUM_METRIC_COLS).map(i => {
//     return (
//       <GridHeaderCell
//         style={
//           {
//             //   height: HEADER_HEIGHT,
//           }
//         }>
//         {/* Cell {i} */}
//       </GridHeaderCell>
//     );
//   })}
//   <GridHeaderCell
//     cols={NUM_METRIC_COLS}
//     style={{
//       zIndex: 2,
//       //   height: HEADER_HEIGHT,
//     }}>
//     Metrics
//   </GridHeaderCell>

const ValueView: React.FC<{value: any}> = ({value}) => {
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
      }}>
      {text}
    </pre>
  );
};

const trimWhitespace = (str: string) => {
  // Trim leading and trailing whitespace
  return str.replace(/^\s+|\s+$/g, '');
};
