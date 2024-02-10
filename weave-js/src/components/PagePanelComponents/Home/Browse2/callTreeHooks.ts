import {constNumber, opIndex} from '@wandb/weave/core';
import {useNodeValue} from '@wandb/weave/react';
import _ from 'lodash';
import {useMemo} from 'react';

import {
  Call,
  CallFilter,
  callsTableFilter,
  callsTableNode,
  callsTableSelect,
  callsTableSelectTraces,
  feedbackTableNode,
  listSelectAll,
  OpSignature,
  opSignatureFromSpan,
  runFeedbackNode,
  Span,
  SpanWithFeedback,
  StreamId,
} from './callTree';

export const fnRunsNode = (streamId: StreamId, filters: CallFilter) => {
  const rowsNode = callsTableNode(streamId);
  const filtered = callsTableFilter(rowsNode, filters);
  return callsTableSelect(filtered);
};

export const useRuns = (
  streamId: StreamId,
  filters: CallFilter,
  opts?: {skip?: boolean}
): {loading: boolean; result: Span[]} => {
  const traceSpansNode = useMemo(
    () => fnRunsNode(streamId, filters),
    [filters, streamId]
  );

  const traceSpansQuery = useNodeValue(traceSpansNode, {skip: opts?.skip});

  return useMemo(
    () =>
      ({
        loading: traceSpansQuery.loading,
        result: traceSpansQuery.result ?? [],
      } ?? []),
    [traceSpansQuery.loading, traceSpansQuery.result]
  );
};

export const useTraceSpans = (
  streamId: StreamId,
  traceId: string
): {loading: boolean; result: Span[]} => {
  return useRuns(streamId, {traceId});
};

interface TraceSummaryRow {
  trace_id: string;
  span_count: number;
}

export const useTraceSummaries = (streamId: StreamId): TraceSummaryRow[] => {
  const tracesNode = useMemo(() => {
    const callsRowsNode = callsTableNode(streamId);
    return callsTableSelectTraces(callsRowsNode);
  }, [streamId]);
  const tracesQuery = useNodeValue(tracesNode);

  return useMemo(() => tracesQuery.result ?? [], [tracesQuery.result]);
};

export const useFirstCall = (
  streamId: StreamId,
  opUri: string
): {loading: boolean; result?: Span} => {
  const firstCallNode = useMemo(() => {
    const streamTableRowsNode = callsTableNode(streamId);
    const filtered = callsTableFilter(streamTableRowsNode, {opUris: [opUri]});
    const selected = callsTableSelect(filtered);
    return opIndex({arr: selected, index: constNumber(0)});
  }, [opUri, streamId]);

  const firstCallQuery = useNodeValue(firstCallNode);
  return firstCallQuery;
};

export const useOpSignature = (
  streamId: StreamId,
  opUri: string
): {loading: boolean; result?: OpSignature} => {
  const firstCallQuery = useFirstCall(streamId, opUri);
  const firstCall = firstCallQuery.result;

  return useMemo(
    () => ({
      loading: firstCallQuery.loading,
      result: firstCall != null ? opSignatureFromSpan(firstCall) : undefined,
    }),
    [firstCall, firstCallQuery.loading]
  );
};

export const fnFeedbackNode = (entityName: string, projectName: string) => {
  return listSelectAll(feedbackTableNode(entityName, projectName));
};

export const useAllFeedback = (
  entityName: string,
  projectName: string,
  opts?: {skip?: boolean}
) => {
  const feedbackNode = useMemo(
    () => fnFeedbackNode(entityName, projectName),
    [entityName, projectName]
  );
  const feedbackQuery = useNodeValue(feedbackNode, {skip: opts?.skip});
  return useMemo(() => {
    if (opts?.skip) {
      return {loading: false, result: []};
    }
    const feedback = feedbackQuery.result ?? [];
    return {
      loading: feedbackQuery.loading,
      result: feedback,
    };
  }, [feedbackQuery.loading, feedbackQuery.result, opts?.skip]);
};

export const useLastRunFeedback = (
  entityName: string,
  projectName: string,
  runId: string
) => {
  const feedbackNode = useMemo(
    () => listSelectAll(runFeedbackNode(entityName, projectName, runId)),
    [entityName, projectName, runId]
  );
  const feedbackQuery = useNodeValue(feedbackNode);
  return useMemo(() => {
    const feedback = feedbackQuery.result ?? [];
    return {
      loading: feedbackQuery.loading,
      result: feedback[feedback.length - 1]?.feedback ?? {},
    };
  }, [feedbackQuery.loading, feedbackQuery.result]);
};

export const joinRunsWithFeedback = (runs: Call[], feedback: any) => {
  const lastFeedbackByRunId: {[key: string]: any} = {};
  for (const row of feedback) {
    lastFeedbackByRunId[row.run_id] = row.feedback;
  }
  const result = runs.map(run => ({
    ...run,
    feedback: lastFeedbackByRunId[run.span_id],
  }));
  return result;
};

export const useRunsWithFeedback = (
  streamId: StreamId,
  filters: CallFilter,
  skipFeedback?: boolean
): {loading: boolean; result: SpanWithFeedback[]} => {
  const runsQuery = useRuns(streamId, filters);

  // Gets all feedback and does a frontend join!
  // We should use a real join!
  const feedbackQuery = useAllFeedback(
    streamId.entityName,
    streamId.projectName,
    {skip: skipFeedback}
  );

  return useMemo(() => {
    if (runsQuery.loading || feedbackQuery.loading) {
      return {loading: true, result: []};
    }
    if (skipFeedback) {
      return runsQuery;
    }
    // TODO: (HACK) Not sure why we are getting duplicates yet, but duplicates
    //        will mess up the UI downstream, so uniquify here.
    // const runs = runsQuery.result;
    const runs = _.uniqBy(runsQuery.result, r => r.span_id);
    const feedback = feedbackQuery.result ?? [];
    const result = joinRunsWithFeedback(runs ?? [], feedback);
    return {
      loading: false,
      result,
    };
  }, [feedbackQuery.loading, feedbackQuery.result, runsQuery, skipFeedback]);
};
