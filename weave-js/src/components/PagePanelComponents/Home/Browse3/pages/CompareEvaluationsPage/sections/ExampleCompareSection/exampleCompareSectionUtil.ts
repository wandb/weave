import _ from 'lodash';
import {useMemo} from 'react';

import {flattenObjectPreservingWeaveTypes} from '../../../../../Browse2/browse2Util';
import {
  buildCompositeMetricsMap,
  CompositeScoreMetrics,
  resolvePeerDimension,
} from '../../compositeMetricsUtil';
import {getOrderedCallIds} from '../../ecpState';
import {EvaluationComparisonState} from '../../ecpState';
import {PredictAndScoreCall} from '../../ecpTypes';
import {metricDefinitionId} from '../../ecpUtil';
import {resolveScoreMetricValueForPASCall} from '../../ecpUtil';

type RowBase = {
  id: string;
  evaluationCallId: string;
  inputDigest: string;
  inputRef: string;
  input: {[inputKey: string]: any};
  path: string[];
  predictAndScore: PredictAndScoreCall;
};

type FlattenedRow = RowBase & {
  output: {[outputKey: string]: any};
  scores: {[scoreId: string]: number | boolean | undefined};
};

export type PivotedRow = RowBase & {
  output: {[outputKey: string]: {[callId: string]: any}};
  scores: {[scoreId: string]: {[callId: string]: number | boolean}};
};

const aggregateGroupedNestedRows = <T>(
  rows: PivotedRow[],
  field: keyof PivotedRow,
  aggFunc: (vals: any[]) => T
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

const filterNones = (list: any[]) => {
  return list.filter(v => v != null);
};

const rowIsSelected = (
  scores: {
    [dimensionId: string]: {
      [evaluationCallId: string]: number | undefined;
    };
  },
  state: EvaluationComparisonState,
  compositeMetricsMap: CompositeScoreMetrics
) => {
  const compareDims = state.comparisonDimensions;

  if (compareDims == null || compareDims.length === 0) {
    return true;
  }
  return compareDims.every(compareDim => {
    if (
      compareDim.rangeSelection == null ||
      Object.entries(compareDim.rangeSelection).length === 0
    ) {
      return true;
    }
    return Object.entries(compareDim.rangeSelection).every(
      ([evalCallId, range]) => {
        const resolvedPeerDim = resolvePeerDimension(
          compositeMetricsMap,
          evalCallId,
          state.data.scoreMetrics[compareDim.metricId]
        );
        if (resolvedPeerDim == null) {
          return false;
        }
        const values = scores[metricDefinitionId(resolvedPeerDim)];
        if (values[evalCallId] == null) {
          return false;
        }
        const rowVal = values[evalCallId] as number;
        return range.min <= rowVal && rowVal <= range.max;
      }
    );
  });
};

export const useFilteredAggregateRows = (state: EvaluationComparisonState) => {
  const leafDims = useMemo(() => getOrderedCallIds(state), [state]);
  const compositeMetricsMap = useMemo(
    () => buildCompositeMetricsMap(state.data, 'score'),
    [state.data]
  );

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
                const output = predictAndScoreRes._rawPredictTraceData?.output;
                rows.push({
                  id: predictAndScoreRes.callId,
                  evaluationCallId: predictAndScoreRes.evaluationCallId,
                  inputDigest: datasetRow.digest,
                  inputRef: predictAndScoreRes.exampleRef,
                  input: flattenObjectPreservingWeaveTypes({
                    input: datasetRow.val,
                  }),
                  output: flattenObjectPreservingWeaveTypes({output}),
                  scores: Object.fromEntries(
                    [...Object.entries(state.data.scoreMetrics)].map(
                      ([scoreKey, scoreVal]) => {
                        return [
                          scoreKey,
                          resolveScoreMetricValueForPASCall(
                            scoreVal,
                            predictAndScoreRes
                          ),
                        ];
                      }
                    )
                  ),
                  path: [
                    rowDigest,
                    predictAndScoreRes.evaluationCallId,
                    predictAndScoreRes.callId,
                  ],
                  predictAndScore: predictAndScoreRes,
                });
              }
            }
          );
        });
      }
    );
    return rows;
  }, [state.data.resultRows, state.data.inputs, state.data.scoreMetrics]);

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
        output: expandDict(row.output, row.evaluationCallId),
        scores: expandDict(row.scores, row.evaluationCallId),
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
            scores: aggregateGroupedNestedRows(rows, 'scores', vals => {
              const allVals = filterNones(vals);
              if (allVals.length === 0) {
                return undefined;
              }
              return _.mean(
                allVals.map(v => {
                  if (typeof v === 'number') {
                    return v;
                  } else if (typeof v === 'boolean') {
                    return v ? 1 : 0;
                  } else {
                    return 0;
                  }
                })
              );
            }),
            originalRows: rows,
          },
        ];
      })
    );
  }, [pivotedRows]);

  const filteredRows = useMemo(() => {
    const aggregatedAsList = Object.values(aggregatedRows);
    const compareDims = state.comparisonDimensions;
    let res = aggregatedAsList;
    if (compareDims != null && compareDims.length > 0) {
      const allowedDigests = Object.keys(aggregatedRows).filter(digest => {
        return rowIsSelected(
          aggregatedRows[digest].scores,
          state,
          compositeMetricsMap
        );
      });

      res = aggregatedAsList.filter(row =>
        allowedDigests.includes(row.inputDigest)
      );
    }
    if (compareDims != null && compareDims.length > 0) {
      // Sort by the difference between the max and min values
      const compareDim = compareDims[0];
      res = _.sortBy(res, row => {
        const values =
          aggregatedRows[row.inputDigest].scores[compareDim.metricId];
        const valuesAsNumbers = Object.values(values).map(v => {
          if (typeof v === 'number') {
            return v;
          } else if (typeof v === 'boolean') {
            return v ? 1 : 0;
          } else {
            return 0;
          }
        });
        return -(Math.max(...valuesAsNumbers) - Math.min(...valuesAsNumbers));
      });
    }
    return res;
  }, [aggregatedRows, compositeMetricsMap, state]);

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
