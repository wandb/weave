import _ from 'lodash';
import {useMemo} from 'react';

import {flattenObject} from '../../../../../Browse2/browse2Util';
import { getOrderedCallIds } from '../../ecpState';
import {EvaluationComparisonState} from '../../ecpTypes';
import { dimensionId, resolveDimensionValueForPASCall } from '../../ecpUtil';

type FlattenedRow = {
  id: string;
  evaluationCallId: string;
  inputDigest: string;
  inputRef: string;
  input: {[inputKey: string]: any};
  output: {[outputKey: string]: any};
  scores: {[scoreId: string]: number | boolean | undefined};
  latency: number;
  totalTokens: number;
  path: string[];
};
type PivotedRow = {
  id: string;
  inputDigest: string;
  inputRef: string;
  input: {[inputKey: string]: any};
  evaluationCallId: string;
  // evaluationCallId: {[callId: string]: string};
  output: {[outputKey: string]: {[callId: string]: any}};
  scores: {[scoreId: string]: {[callId: string]: number | boolean}};
  latency: {[callId: string]: number};
  totalTokens: {[callId: string]: number};
  path: string[];
};
const aggregateGroupedNestedRows = (
  rows: PivotedRow[],
  field: keyof PivotedRow,
  aggFunc: (vals: any[]) => any
) => {
  return Object.fromEntries(
    Object.entries(
      rows.reduce<{
        [flatKey: string]: {[callId: string]: any[]};
      }>((acc, row) => {
        Object.entries(row[field]).forEach(([key, val]) => {
          Object.entries(val).forEach(([subKey, subVal]) => {
            if (acc[key] == null) {
              acc[key] = {};
            }
            if (acc[key][subKey] == null) {
              acc[key][subKey] = [];
            }
            acc[key][subKey].push(subVal);
          });
        });
        return acc;
      }, {})
    ).map(([key, val]) => {
      return [
        key,
        Object.fromEntries(
          Object.entries(val).map(([subKey, subVal]) => {
            return [subKey, aggFunc(subVal)];
          })
        ),
      ];
    })
  );
};
const aggregateGroupedRows = (
  rows: PivotedRow[],
  field: keyof PivotedRow,
  aggFunc: (vals: any[]) => any
) => {
  return Object.fromEntries(
    Object.entries(
      rows.reduce<{
        [flatKey: string]: any[];
      }>((acc, row) => {
        Object.entries(row[field]).forEach(([key, val]) => {
          if (acc[key] == null) {
            acc[key] = [];
          }
          acc[key].push(val);
        });

        return acc;
      }, {})
    ).map(([key, val]) => {
      return [key, aggFunc(val)];
    })
  );
};
const filterNones = (list: any[]) => {
  return list.filter(v => v != null);
};
export const useFilteredAggregateRows = (state: EvaluationComparisonState) => {
  const leafDims = useMemo(() => getOrderedCallIds(state), [state]);


  const flattenedRows = useMemo(() => {
    const rows: FlattenedRow[] = [];
    Object.entries(state.data.resultRows).forEach(
      ([rowDigest, rowCollection]) => {
        Object.values(rowCollection.evaluations).forEach(modelCollection => {
          Object.values(modelCollection.predictAndScores).forEach(
            predictAndScoreRes => {
              const datasetRow =
                state.data.inputs[predictAndScoreRes.rowDigest];
              if (datasetRow != null) {
                const output = predictAndScoreRes._legacy_predictCall?.output;
                rows.push({
                  // ...predictAndScoreRes,
                  id: predictAndScoreRes.callId,
                  evaluationCallId: predictAndScoreRes.evaluationCallId,
                  inputDigest: datasetRow.digest,
                  inputRef: predictAndScoreRes.firstExampleRef,
                  input: flattenObject({input: datasetRow.val}),
                  output: flattenObject({output}),
                  latency: predictAndScoreRes._legacy_predictCall?.latencyMs ?? 0,
                  totalTokens:
                    predictAndScoreRes._legacy_predictCall?.totalUsageTokens ?? 0,
                  scores: Object.fromEntries(
                    Object.entries(state.data.scorerMetricDimensions).map(([scoreKey, scoreVal]) => {
                      return [
                        scoreKey,
                        resolveDimensionValueForPASCall(
                          scoreVal, predictAndScoreRes
                        )
                      ];
                    })
                  ),
                  path: [
                    rowDigest,
                    predictAndScoreRes.evaluationCallId,
                    predictAndScoreRes.callId,
                  ],
                });
              }
            }
          );
        });
      }
    );
    return rows;
  }, [state.data.resultRows, state.data.inputs, state.data.scorerMetricDimensions]);

  // const filteredDigests = useMemo(() => {
  // }, []);
  // console.log({flattenedRows, scoreMap});
  const pivotedRows = useMemo(() => {
    // Ok, so in this step we are going to pivot -
    // id: string; - no change
    // inputDigest: string; - no change
    // input: {[inputKey: string]: any}; - no change
    // evaluationCallId: string; - Each key will be divided into new leafs
    // output: {[outputKey: string]: any}; - Each key will be divided into new leafs
    // scores: {[scoreId: string]: number | boolean}; - Each key will be divided into new leafs
    // latency: number; - Each key will be divided into new leafs
    // totalTokens: number; - Each key will be divided into new leafs
    // path: string[]; - no change
    const expandPrimitive = (obj: any, evaluationCallId: string) => {
      return Object.fromEntries(
        leafDims.map(d => {
          return [d, evaluationCallId === d ? obj : null];
        })
      );
    };

    const expandDict = (obj: any, evaluationCallId: string) => {
      return Object.fromEntries(
        Object.entries(obj).map(([key, val]) => {
          return [key, expandPrimitive(val, evaluationCallId)];
        })
      );
    };

    return flattenedRows.map(row => {
      return {
        ...row,

        // evaluationCallId: expandPrimitive(
        //   row.evaluationCallId,
        //   row.evaluationCallId
        // ),
        output: expandDict(row.output, row.evaluationCallId),
        scores: expandDict(row.scores, row.evaluationCallId),
        latency: expandPrimitive(row.latency, row.evaluationCallId),
        totalTokens: expandPrimitive(row.totalTokens, row.evaluationCallId),
      };
    }) as PivotedRow[];
  }, [flattenedRows, leafDims]);

  const aggregatedRows = useMemo(() => {
    const grouped = _.groupBy(pivotedRows, row => row.inputDigest);
    return Object.fromEntries(
      Object.entries(grouped).map(([inputDigest, rows]) => {
        return [
          inputDigest,
          {
            id: inputDigest, // required for the data grid
            count: rows.length,
            inputDigest,
            inputRef: rows[0].inputRef, // Should be the same for all,
            input: rows[0].input, // Should be the same for all
            output: aggregateGroupedNestedRows(
              rows,
              'output',
              vals => filterNones(vals)[0]
            ),
            scores: aggregateGroupedNestedRows(rows, 'scores', vals =>
              _.mean(
                filterNones(vals).map(v => {
                  if (typeof v === 'number') {
                    return v;
                  } else if (typeof v === 'boolean') {
                    return v ? 100 : 0;
                  } else {
                    return 0;
                  }
                })
              )
            ),
            latency: aggregateGroupedRows(rows, 'latency', vals =>
              _.mean(filterNones(vals))
            ),
            totalTokens: aggregateGroupedRows(rows, 'totalTokens', vals =>
              _.mean(filterNones(vals))
            ),
            originalRows: rows,
          },
        ];
      })
    );
  }, [pivotedRows]);

  const filteredRows = useMemo(() => {
    const aggregatedAsList = Object.values(aggregatedRows);
    const compareDim = state.comparisonDimension;
    if (state.rangeSelection && Object.keys(state.rangeSelection).length > 0 && compareDim != null) {
      const allowedDigests = Object.keys(aggregatedRows).filter(digest => {
        const values =
          aggregatedRows[digest].scores[
            dimensionId(compareDim)
          ];
        return Object.entries(state.rangeSelection).every(([key, val]) => {
          return val.min <= values[key] && values[key] <= val.max;
        });
      });
      // console.log(
      //   'Filtering',
      //   state.comparisonDimension,
      //   state.rangeSelection,
      //   aggregatedRows,
      //   allowedDigests
      // );
      return aggregatedAsList.filter(row =>
        allowedDigests.includes(row.inputDigest)
      );
    }
    return aggregatedAsList;
  }, [aggregatedRows, state.comparisonDimension, state.rangeSelection]);

  const inputColumnKeys = useMemo(() => {
    const keys = new Set<string>();
    const keysList: string[] = [];
    flattenedRows.forEach(row => {
      Object.keys(row.input).forEach(key => {
        if (!keys.has(key)) {
          keys.add(key);
          keysList.push(key);
        }
      });
    });
    return keysList;
  }, [flattenedRows]);

  const outputColumnKeys = useMemo(() => {
    const keys = new Set<string>();
    const keysList: string[] = [];
    flattenedRows.forEach(row => {
      Object.keys(row.output).forEach(key => {
        if (!keys.has(key)) {
          keys.add(key);
          keysList.push(key);
        }
      });
    });
    return keysList;
  }, [flattenedRows]);

  return useMemo(() => {
    return {
      filteredRows,
      inputColumnKeys,
      outputColumnKeys,
      leafDims,
    };
  }, [filteredRows, inputColumnKeys, leafDims, outputColumnKeys]);
};

