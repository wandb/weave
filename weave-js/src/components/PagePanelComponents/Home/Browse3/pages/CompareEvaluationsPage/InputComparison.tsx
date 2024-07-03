import _ from 'lodash';
import React from 'react';
import styled from 'styled-components';

import {HorizontalBox, VerticalBox} from './Layout';
import {EvaluationComparisonState} from './types';
import {useFilteredAggregateRows} from './comparisonTableUtil';
import {WeaveObjectRef, parseRef} from '../../../../../../react';
import {SmallRef} from '../../../Browse2/SmallRef';

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
// _.range(NUM_METRIC_COLS).map(i => {
//     return (
//       <GridCell
//         // rows={NUM_INPUT_PROPS}
//         style={{
//           writingMode: 'vertical-rl',
//           transform: 'rotate(180deg)',
//         }}>
//         Cell
//       </GridCell>
//     );
//   })}
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

  const NUM_SCORERS = 2;
  const NUM_METRICS_PER_SCORER = 2;
  const NUM_METRICS = NUM_SCORERS * NUM_METRICS_PER_SCORER;
  const NUM_METRIC_COLS = NUM_METRICS + 1;
  const NUM_COLS =
    1 + // Input / Eval Title
    2 + // Input Prop Key / Val
    NUM_METRIC_COLS;
  const NUM_INPUT_PROPS = inputColumnKeys.length;
  const NUM_OUTPUT_KEYS = 3;
  const NUM_EVALS = 3;
  const FREE_TEXT_COL_NDX = 2;
  const NUM_TRIALS = 10;
  const HEADER_HEIGHT = 40;

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
            flex: 1,
            display: 'grid',
            overflow: 'auto',
          }}>
          <GridCell rows={NUM_INPUT_PROPS}>
            <SmallRef objRef={inputRef} iconOnly />
          </GridCell>
          {_.range(NUM_INPUT_PROPS).map(i => {
            return (
              <React.Fragment key={inputColumnKeys[i]}>
                <GridCell>{inputColumnKeys[i]}</GridCell>
                <GridCell>
                  {target.input[inputColumnKeys[i]].toString()}
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
                        // position: 'sticky',
                        //   top: HEADER_HEIGHT,
                        // top: 0,
                        backgroundColor: 'lightgray',
                        // zIndex: 1,
                      }}>
                      Trials
                    </GridCell>
                    {_.range(NUM_SCORERS).map(si => {
                      return (
                        <>
                          <GridCell
                            cols={NUM_METRICS_PER_SCORER}
                            // rows={NUM_INPUT_PROPS + 1}
                            style={{
                              backgroundColor: 'lightgray',
                            }}>
                            Scorer {si}
                          </GridCell>
                        </>
                      );
                    })}
                    {_.range(NUM_METRICS_PER_SCORER * NUM_SCORERS).map(i => {
                      return (
                        <GridCell
                          //   rows={NUM_INPUT_PROPS}
                          style={{
                            ...verticalStyle,
                            // position: 'sticky',
                            //   top: HEADER_HEIGHT,
                            // top: 0,
                            backgroundColor: 'lightgray',
                            // zIndex: 1,
                          }}>
                          Metric {i}
                        </GridCell>
                      );
                    })}
                  </GridCell>
                )}
              </React.Fragment>
            );
          })}
          {_.range(NUM_EVALS).map(ei => {
            return (
              <>
                {/* <GridCell cols={NUM_COLS}>Eval Title {ei}</GridCell> */}
                <GridCell rows={NUM_OUTPUT_KEYS}>Eval Title {ei}</GridCell>
                {_.range(NUM_OUTPUT_KEYS).map(oi => {
                  return (
                    <>
                      <GridCell>Output Prop {oi} Key</GridCell>
                      <GridCell>Output Prop {oi} Val</GridCell>
                      {oi === 0 && (
                        <GridCell
                          rows={NUM_OUTPUT_KEYS}
                          cols={NUM_METRIC_COLS}
                          style={{
                            display: 'grid',
                            gridTemplateColumns: 'subgrid',
                            maxHeight: '300px',
                            overflow: 'auto',
                          }}>
                          <GridHeaderCell>5</GridHeaderCell>
                          {_.range(NUM_METRICS).map(i => {
                            return <GridHeaderCell>V{i} +/-123</GridHeaderCell>;
                          })}
                          {_.range(NUM_TRIALS).map(i => {
                            return (
                              <>
                                <GridCell>{i}</GridCell>
                                {_.range(NUM_METRICS).map(i => {
                                  return <GridCell>S{i}</GridCell>;
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
