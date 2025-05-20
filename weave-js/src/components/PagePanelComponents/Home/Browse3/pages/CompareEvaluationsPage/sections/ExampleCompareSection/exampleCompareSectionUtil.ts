import {isWeaveObjectRef, ObjectRef, parseRefMaybe} from '@wandb/weave/react';
import _ from 'lodash';
import {useEffect, useMemo, useState} from 'react';

import {flattenObjectPreservingWeaveTypes} from '../../../../flattenObject';
import {TraceServerClient} from '../../../wfReactInterface/traceServerClient';
import {useGetTraceServerClientContext} from '../../../wfReactInterface/traceServerClientContext';
import {TraceTableQueryReq} from '../../../wfReactInterface/traceServerClientTypes';
import {projectIdFromParts} from '../../../wfReactInterface/tsDataModelHooks';
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

export type FilteredAggregateRows = {
  id: string;
  count: number;
  inputDigest: string;
  inputRef: ObjectRef | null;
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
}[];

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
  const partialTableRequest = usePartialTableRequest(state);

  useEffect(() => {
    (async () => {
      // Nothing we can do if the partial table request is not set
      if (partialTableRequest == null) {
        return;
      }
      await loadMissingRowDataIntoCache(
        client,
        ctx,
        prefetchDigests,
        partialTableRequest
      );
    })();
  }, [partialTableRequest, client, prefetchDigests, state, ctx]);

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
  const partialTableRequest = usePartialTableRequest(state);

  useEffect(() => {
    let mounted = true;
    (async () => {
      let cachedRowData = ctx.getCachedRowData(targetDigest);
      // If the value is already loaded, don't fetch again
      if (cachedRowData != null) {
        setTargetRowValue(flattenObjectPreservingWeaveTypes(cachedRowData));
        return;
      }
      // Nothing we can do if the partial table request is not set
      if (partialTableRequest == null) {
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
  }, [partialTableRequest, client, ctx, targetDigest]);

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
const usePartialTableRequest = (state: EvaluationComparisonState) => {
  const getTraceServerClient = useGetTraceServerClientContext();
  const client = getTraceServerClient();
  const [partialTableRequest, setPartialTableRequest] =
    useState<PartialTableRequestType | null>(null);

  const datasetRef = useMemo(() => {
    return Object.values(state.summary.evaluations)[0].datasetRef as string;
  }, [state.summary.evaluations]);

  useEffect(() => {
    let mounted = true;
    makePartialTableReq(client, datasetRef).then(res => {
      if (mounted) {
        setPartialTableRequest(res);
      }
    });
    return () => {
      mounted = false;
    };
  }, [client, datasetRef]);

  return partialTableRequest;
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
