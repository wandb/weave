import {isWeaveObjectRef, ObjectRef, parseRefMaybe} from '@wandb/weave/react';
import _ from 'lodash';
import {useEffect, useMemo, useState} from 'react';

import {flattenObjectPreservingWeaveTypes} from '../../../../../flattenObject';
import {TraceServerClient} from '../../../../wfReactInterface/traceServerClient';
import {useGetTraceServerClientContext} from '../../../../wfReactInterface/traceServerClientContext';
import {TraceTableQueryReq} from '../../../../wfReactInterface/traceServerClientTypes';
import {projectIdFromParts} from '../../../../wfReactInterface/tsDataModelHooks';
import {CompareEvaluationContext} from '../../compareEvaluationsContext';
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
  trialNdx: number;
};

export type PivotedRow = RowBase & {
  output: {[outputKey: string]: {[callId: string]: any}};
  scores: {[scoreId: string]: {[callId: string]: number | boolean | undefined}};
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

export type FilteredAggregateRow = {
  id: string;
  count: number;
  inputDigest: string;
  inputRef: ObjectRef | null;
  inputRefs: Set<string>; // All unique input refs for this digest
  output: {
    [k: string]: {
      [k: string]: any;
    };
  };
  scores: {
    [k: string]: {
      [k: string]: number | undefined;
    };
  };
  originalRows: PivotedRow[];
};

export type FilteredAggregateRows = FilteredAggregateRow[];

export const useFilteredAggregateRows = (
  state: EvaluationComparisonState
): {
  filteredRows: FilteredAggregateRows;
  outputColumnKeys: string[];
  leafDims: string[];
} => {
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
          (predictAndScoreRes, trialNdx) => {
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
              trialNdx,
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
    const result: {[inputDigest: string]: FilteredAggregateRow} =
      Object.fromEntries(
        Object.entries(grouped).map(([inputDigest, rows]) => {
          // Collect all unique input refs for this digest
          const uniqueInputRefs = new Set<string>();
          rows.forEach(row => {
            if (row.inputRef) {
              uniqueInputRefs.add(row.inputRef);
            }
          });

          const aggregatedRow: FilteredAggregateRow = {
            id: inputDigest, // required for the data grid
            count: rows.length,
            inputDigest,
            inputRef: parseRefMaybe(rows[0].inputRef), // Keep for backwards compatibility
            inputRefs: uniqueInputRefs, // All unique input refs
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
          };

          return [inputDigest, aggregatedRow];
        })
      );
    return result;
  }, [pivotedRows]);

  const filteredRows = useMemo((): FilteredAggregateRows => {
    const aggregatedAsList = Object.values(aggregatedRows);
    const compareDims = state.comparisonDimensions;
    let res: FilteredAggregateRows = aggregatedAsList;
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

/**
 * The following functions are used to fetch data rows There are the following methods:
 * * `useExampleCompareDataAndPrefetch` - This is used to fetch a target row and prefetch the adjacent rows.
 *   * This is the primary exported hook from this section.
 * * `useExampleCompareData` - This is used to fetch a single row.
 * * `loadMissingRowDataIntoCache` - This is used to asynchronously load rows that are not yet in our cache.
 * * Then there are a few helper functions that are used to make the above hooks work:
 *   * `makePartialTableReq` - This is used to make a partial table request for a dataset.
 *   * `usePartialTableRequest` - This is used to wrap the `makePartialTableReq` hook and provide a reactive partial table request.
 *   * `loadRowDataIntoCache` - This is used to directly load rows into our cache.
 *   * `getCachedRowData` - This is used to directly get a row from our cache.
 */

// React hook to wrap the `useExampleCompareData` and `prefetchRowData`
// to provide a single hook that fetches the target row and prefetches the adjacent rows
// This is a convenience hook for the `ExampleCompareSection` component
export function useExampleCompareDataAndPrefetch(
  ctx: CompareEvaluationContext,
  filteredRows: Array<{
    inputDigest: string;
  }>,
  targetIndex: number
) {
  const {state} = ctx;
  // Step 1: Fetch the target row
  const targetDigest = filteredRows[targetIndex].inputDigest;
  const {targetRowValue, loading} = useExampleCompareData(ctx, targetDigest);

  // Step 2: Prefetch the adjacent rows
  const prefetchDigests = useMemo(() => {
    const digests = [];
    if (targetIndex > 0) {
      digests.push(filteredRows[targetIndex - 1].inputDigest);
    }
    if (targetIndex < filteredRows.length - 1) {
      digests.push(filteredRows[targetIndex + 1].inputDigest);
    }
    return digests;
  }, [filteredRows, targetIndex]);
  const getTraceServerClient = useGetTraceServerClientContext();
  const client = getTraceServerClient();
  const partialTableRequests = usePartialTableRequests(state);

  useEffect(() => {
    (async () => {
      // Nothing we can do if no partial table requests are available
      if (Object.keys(partialTableRequests).length === 0) {
        return;
      }

      // For each prefetch digest, determine its dataset and load if needed
      for (const digest of prefetchDigests) {
        const rowData =
          state.loadableComparisonResults.result?.resultRows?.[digest];
        if (!rowData) continue;

        // Find the dataset ref for this row
        const evalCallId = Object.keys(rowData.evaluations)[0];
        if (!evalCallId) continue;

        const evaluationCall = state.summary.evaluationCalls[evalCallId];
        if (!evaluationCall) continue;

        const evaluation =
          state.summary.evaluations[evaluationCall.evaluationRef];
        const datasetRef = evaluation?.datasetRef;
        if (!datasetRef) continue;

        const partialTableRequest = partialTableRequests[datasetRef];
        if (!partialTableRequest) continue;

        await loadMissingRowDataIntoCache(
          client,
          ctx,
          [digest],
          partialTableRequest
        );
      }
    })();
  }, [partialTableRequests, client, prefetchDigests, state, ctx]);

  return {
    targetRowValue,
    loading,
  };
}

// Primary method for fetching and caching a single row
export function useExampleCompareData(
  ctx: CompareEvaluationContext,
  targetDigest: string
) {
  const {state} = ctx;
  const initialValue = ctx.getCachedRowData(targetDigest);
  const [loading, setLoading] = useState<boolean>(initialValue == null);
  const [targetRowValue, setTargetRowValue] = useState<any>(
    initialValue ? flattenObjectPreservingWeaveTypes(initialValue) : null
  );
  const getTraceServerClient = useGetTraceServerClientContext();
  const client = getTraceServerClient();
  const partialTableRequests = usePartialTableRequests(state);

  // Determine which dataset to use for this row by checking which evaluations have data for it
  const datasetRefForRow = useMemo(() => {
    // Check which evaluations have data for this digest
    const rowData =
      state.loadableComparisonResults.result?.resultRows?.[targetDigest];
    if (!rowData) return null;

    // Find the first evaluation that has data for this row
    const evalCallId = Object.keys(rowData.evaluations)[0];
    if (!evalCallId) return null;

    // Get the dataset ref from that evaluation
    const evaluationCall = state.summary.evaluationCalls[evalCallId];
    if (!evaluationCall) return null;

    const evaluation = state.summary.evaluations[evaluationCall.evaluationRef];
    return evaluation?.datasetRef;
  }, [state, targetDigest]);

  useEffect(() => {
    let mounted = true;
    (async () => {
      let cachedRowData = ctx.getCachedRowData(targetDigest);
      // If the value is already loaded, don't fetch again
      if (cachedRowData != null) {
        setTargetRowValue(flattenObjectPreservingWeaveTypes(cachedRowData));
        return;
      }

      // If we couldn't determine the dataset ref, we can't fetch the row
      if (!datasetRefForRow) {
        setLoading(false);
        return;
      }

      // Get the partial table request for this dataset
      const partialTableRequest = partialTableRequests[datasetRefForRow];
      if (!partialTableRequest) {
        // Partial table request not ready yet
        return;
      }

      // immediately fetch the current row
      setLoading(true);

      const singleRows = await loadRowDataIntoCache(
        client,
        ctx,
        [targetDigest],
        partialTableRequest
      );
      if (mounted) {
        const data = singleRows[0];
        if (data != null) {
          setTargetRowValue(flattenObjectPreservingWeaveTypes(data));
        }
        setLoading(false);
      }
    })();
    return () => {
      mounted = false;
    };
  }, [partialTableRequests, client, ctx, targetDigest, datasetRefForRow]);

  return {
    targetRowValue,
    loading,
  };
}

// Helper to load rows that are not yet in our cache
async function loadMissingRowDataIntoCache(
  client: TraceServerClient,
  ctx: CompareEvaluationContext,
  rowDigests: string[],
  partialTableRequest: PartialTableRequestType
): Promise<any[]> {
  const neededRows = rowDigests.filter(
    row => ctx.getCachedRowData(row) == null
  );

  if (neededRows.length > 0) {
    // we load the data into the cache, but don't trigger a re-render
    await loadRowDataIntoCache(client, ctx, neededRows, partialTableRequest);
  }

  return rowDigests.map(row => ctx.getCachedRowData(row));
}

type PartialTableRequestType = Pick<
  TraceTableQueryReq,
  'project_id' | 'digest'
>;

// Get the table digest used in the dataset of the first evaluation,
// which prepares a request for actually fetching the table rows later
async function makePartialTableReq(
  client: TraceServerClient,
  datasetRef: string
): Promise<PartialTableRequestType | null> {
  const datasetObjRes = await client.readBatch({
    refs: [datasetRef],
  });
  if (!datasetObjRes.vals[0]) {
    console.error('Dataset not found');
    return null;
  }

  const rowsRef = datasetObjRes.vals[0].rows;
  const parsedRef = parseRefMaybe(rowsRef);
  if (parsedRef == null) {
    console.error('Invalid rows ref', rowsRef);
    return null;
  }
  if (!isWeaveObjectRef(parsedRef)) {
    console.error('Ref is not a weave object ref', rowsRef);
    return null;
  }
  if (parsedRef.weaveKind !== 'table') {
    console.error('Ref is not a table ref', rowsRef);
    return null;
  }

  return {
    project_id: projectIdFromParts({
      entity: parsedRef.entityName,
      project: parsedRef.projectName,
    }),
    digest: parsedRef.artifactVersion,
  };
}

// React hook to wrap the `makePartialTableReq`
// This now returns a map of dataset refs to their partial table requests
const usePartialTableRequests = (state: EvaluationComparisonState) => {
  const getTraceServerClient = useGetTraceServerClientContext();
  const client = getTraceServerClient();
  const [partialTableRequests, setPartialTableRequests] = useState<{
    [datasetRef: string]: PartialTableRequestType;
  }>({});

  const datasetRefs = useMemo(() => {
    // Get all unique dataset refs from all evaluations
    const refs = new Set<string>();
    Object.values(state.summary.evaluations).forEach(evaluation => {
      if (evaluation.datasetRef) {
        refs.add(evaluation.datasetRef);
      }
    });
    return Array.from(refs);
  }, [state.summary.evaluations]);

  useEffect(() => {
    let mounted = true;

    // Fetch partial table requests for all datasets
    Promise.all(
      datasetRefs.map(async datasetRef => {
        const req = await makePartialTableReq(client, datasetRef);
        return {datasetRef, req};
      })
    ).then(results => {
      if (mounted) {
        const newRequests: {[datasetRef: string]: PartialTableRequestType} = {};
        results.forEach(({datasetRef, req}) => {
          if (req) {
            newRequests[datasetRef] = req;
          }
        });
        setPartialTableRequests(newRequests);
      }
    });

    return () => {
      mounted = false;
    };
  }, [client, datasetRefs]);

  return partialTableRequests;
};

// Helper to fetch and store row data in our state cache
async function loadRowDataIntoCache(
  client: TraceServerClient,
  ctx: CompareEvaluationContext,
  rowDigests: string[],
  partialTableRequest: PartialTableRequestType
): Promise<any[]> {
  const rowsRes = await client.tableQuery({
    ...partialTableRequest,
    filter: {
      row_digests: rowDigests,
    },
  });
  for (const row of rowsRes.rows) {
    ctx.setCachedRowData(row.digest, row.val);
  }
  return rowsRes.rows.map(row => row.val);
}

export const removePrefix = (key: string, prefix: string) => {
  if (key.startsWith(prefix)) {
    return key.slice(prefix.length);
  }
  return key;
};
