import {parseRef, parseRefMaybe, WeaveObjectRef} from '@wandb/weave/react';
import _, {isEmpty} from 'lodash';
import {
  MutableRefObject,
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
} from 'react';

import {flattenObjectPreservingWeaveTypes} from '../../../../flattenObject';
import {TraceServerClient} from '../../../wfReactInterface/traceServerClient';
import {useGetTraceServerClientContext} from '../../../wfReactInterface/traceServerClientContext';
import {projectIdFromParts} from '../../../wfReactInterface/tsDataModelHooks';
import {
  buildCompositeMetricsMap,
  CompositeScoreMetrics,
  resolvePeerDimension,
} from '../../compositeMetricsUtil';
import {EvaluationComparisonState, getOrderedCallIds} from '../../ecpState';
import {PredictAndScoreCall} from '../../ecpTypes';
import {
  metricDefinitionId,
  resolveScoreMetricValueForPASCall,
} from '../../ecpUtil';

type RowBase = {
  id: string;
  evaluationCallId: string;
  inputDigest: string;
  inputRef: string;
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
          state.summary.scoreMetrics[compareDim.metricId]
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
    () => buildCompositeMetricsMap(state.summary, 'score'),
    [state.summary]
  );

  const flattenedRows = useMemo(() => {
    const rows: FlattenedRow[] = [];
    Object.entries(
      state.loadableComparisonResults.result?.resultRows ?? {}
    ).forEach(([rowDigest, rowCollection]) => {
      Object.values(rowCollection.evaluations).forEach(modelCollection => {
        Object.values(modelCollection.predictAndScores).forEach(
          predictAndScoreRes => {
            const output = predictAndScoreRes._rawPredictTraceData?.output;
            rows.push({
              id: predictAndScoreRes.callId,
              evaluationCallId: predictAndScoreRes.evaluationCallId,
              inputDigest: predictAndScoreRes.rowDigest,
              inputRef: predictAndScoreRes.exampleRef,
              // Note: this would be a possible location to record the raw predict_and_score inputs as the presumed data row.
              output: flattenObjectPreservingWeaveTypes({output}),
              scores: Object.fromEntries(
                [...Object.entries(state.summary.scoreMetrics)].map(
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
        );
      });
    });
    return rows;
  }, [
    state.loadableComparisonResults.result?.resultRows,
    state.summary.scoreMetrics,
  ]);

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
            inputRef: parseRefMaybe(rows[0].inputRef), // Should be the same for all,
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
      outputColumnKeys,
      leafDims,
    };
  }, [filteredRows, leafDims, outputColumnKeys]);
};

// Get the table digest used in the dataset of the first evaluation,
// which prepares a request for actually fetching the table rows later
async function makePartialTableReq(
  evaluations: UseExampleCompareDataParams[0]['summary']['evaluations'],
  filteredRows: UseExampleCompareDataParams[1],
  targetIndex: UseExampleCompareDataParams[2],
  getTraceServerClient: () => TraceServerClient
) {
  const targetRow = filteredRows[targetIndex];
  if (targetRow == null) {
    return null;
  }
  const datasetRef = Object.values(evaluations)[0].datasetRef as string;

  const datasetObjRes = await getTraceServerClient().readBatch({
    refs: [datasetRef],
  });
  if (!datasetObjRes.vals[0]) {
    console.error('Dataset not found');
    return null;
  }

  const rowsRef = datasetObjRes.vals[0].rows;
  const parsedRowsRef = parseRef(rowsRef) as WeaveObjectRef;

  return {
    project_id: projectIdFromParts({
      entity: parsedRowsRef.entityName,
      project: parsedRowsRef.projectName,
    }),
    digest: parsedRowsRef.artifactVersion,
  };
}

async function loadRowDataIntoCache(
  rowDigests: string[],
  cachedRowData: MutableRefObject<Record<string, any>>,
  cachedPartialTableRequest: MutableRefObject<{
    project_id: string;
    digest: string;
  } | null>,
  getTraceServerClient: () => TraceServerClient
) {
  const rowsRes = await getTraceServerClient().tableQuery({
    ...cachedPartialTableRequest.current!,
    filter: {
      row_digests: rowDigests,
    },
  });
  for (const row of rowsRes.rows) {
    cachedRowData.current[row.digest] = row.val;
  }
}

type UseExampleCompareDataParams = Parameters<typeof useExampleCompareData>;

export function useExampleCompareData(
  state: EvaluationComparisonState,
  filteredRows: Array<{
    inputDigest: string;
  }>,
  targetIndex: number
) {
  const getTraceServerClient = useGetTraceServerClientContext();

  // cache the row data for the current target row and adjacent rows,
  // this is to allow for fast re-renders during pagination
  const cachedRowData = useRef<Record<string, any>>({});
  const cachedPartialTableRequest = useRef<{
    project_id: string;
    digest: string;
  } | null>(null);

  // This is to provide a way to manually control the re-render of the target row
  const [cacheVersion, setCacheVersion] = useState<number>(0);
  const increaseCacheVersion = useCallback(() => {
    setCacheVersion(prev => prev + 1);
  }, []);

  const [loading, setLoading] = useState<boolean>(false);

  const targetRowValue = useMemo(() => {
    if (isEmpty(filteredRows)) {
      return undefined;
    }
    const digest = filteredRows[targetIndex].inputDigest;
    return flattenObjectPreservingWeaveTypes(cachedRowData.current[digest]);
    // Including `cacheVersion` in the dependency array ensures the memo recalculates
    // when it changes, even though it's not directly used in the calculation.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [cacheVersion, filteredRows, targetIndex]);

  useEffect(() => {
    (async () => {
      const targetRow = filteredRows[targetIndex];
      if (targetRow == null) {
        return;
      }

      const selectedRowDigest = targetRow.inputDigest;

      if (!cachedPartialTableRequest.current) {
        cachedPartialTableRequest.current = await makePartialTableReq(
          state.summary.evaluations,
          filteredRows,
          targetIndex,
          getTraceServerClient
        );
      }

      if (cachedPartialTableRequest.current == null) {
        // couldn't get the table digest, no way to proceed
        return;
      }

      if (!(selectedRowDigest in cachedRowData.current)) {
        // immediately fetch the current row
        setLoading(true);

        await loadRowDataIntoCache(
          [selectedRowDigest],
          cachedRowData,
          cachedPartialTableRequest,
          getTraceServerClient
        );

        // This trigger a re-calculation of the `target` and a re-render immediately
        increaseCacheVersion();
        setLoading(false);
      }

      // check if there is a need to fetch adjacent rows
      const adjacentRows = [];
      if (targetIndex > 0) {
        adjacentRows.push(filteredRows[targetIndex - 1].inputDigest);
      }
      if (targetIndex < filteredRows.length - 1) {
        adjacentRows.push(filteredRows[targetIndex + 1].inputDigest);
      }

      const adjacentRowsToFetch = adjacentRows.filter(
        row => !(row in cachedRowData.current)
      );

      if (adjacentRowsToFetch.length > 0) {
        // we load the data into the cache, but don't trigger a re-render
        await loadRowDataIntoCache(
          adjacentRowsToFetch,
          cachedRowData,
          cachedPartialTableRequest,
          getTraceServerClient
        );
      }

      // evict the obsolete cache
      const newCache: Record<string, any> = {};
      for (const rowDigest of [selectedRowDigest, ...adjacentRows]) {
        newCache[rowDigest] = cachedRowData.current[rowDigest];
      }
      cachedRowData.current = newCache;
    })();
  }, [
    state.summary.evaluations,
    filteredRows,
    targetIndex,
    increaseCacheVersion,
    getTraceServerClient,
  ]);

  return {
    targetRowValue,
    loading,
  };
}
