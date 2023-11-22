import {constNumber, opIndex} from '@wandb/weave/core';
import {useNodeValue} from '@wandb/weave/react';
import {useMemo} from 'react';

import {
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

export const useRuns = (
  streamId: StreamId,
  filters: CallFilter
): {loading: boolean; result: Span[]} => {
  const traceSpansNode = useMemo(() => {
    const rowsNode = callsTableNode(streamId);
    const filtered = callsTableFilter(rowsNode, filters);
    return callsTableSelect(filtered);
  }, [filters, streamId]);
  const traceSpansQuery = useNodeValue(traceSpansNode);

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
    const filtered = callsTableFilter(streamTableRowsNode, {opUri});
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

export const useAllFeedback = (entityName: string, projectName: string) => {
  const feedbackNode = useMemo(
    () => listSelectAll(feedbackTableNode(entityName, projectName)),
    [entityName, projectName]
  );
  const feedbackQuery = useNodeValue(feedbackNode);
  return useMemo(() => {
    const feedback = feedbackQuery.result ?? [];
    return {
      loading: feedbackQuery.loading,
      result: feedback,
    };
  }, [feedbackQuery.loading, feedbackQuery.result]);
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

export const useRunsWithFeedback = (
  streamId: StreamId,
  filters: CallFilter
): {loading: boolean; result: SpanWithFeedback[]} => {
  const runsQuery = useRuns(streamId, filters);

  // Gets all feedback and does a frontend join!
  // We should use a real join!
  const feedbackQuery = useAllFeedback(
    streamId.entityName,
    streamId.projectName
  );

  return useMemo(() => {
    if (runsQuery.loading || feedbackQuery.loading) {
      return {loading: true, result: []};
    }
    const runs = runsQuery.result;
    const feedback = feedbackQuery.result ?? [];
    const lastFeedbackByRunId: {[key: string]: any} = {};
    for (const row of feedback) {
      lastFeedbackByRunId[row.run_id] = row.feedback;
    }
    const result = runs.map(run => ({
      ...run,
      feedback: lastFeedbackByRunId[run.span_id],
    }));
    return {
      loading: false,
      result,
    };
  }, [
    feedbackQuery.loading,
    feedbackQuery.result,
    runsQuery.loading,
    runsQuery.result,
  ]);
};
