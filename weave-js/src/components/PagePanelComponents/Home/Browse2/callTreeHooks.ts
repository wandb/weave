import {useMemo} from 'react';
import {
  StreamId,
  Span,
  callsTableFilter,
  callsTableNode,
  callsTableSelect,
  OpSignature,
  opSignatureFromSpan,
} from './callTree';
import {useNodeValue} from '@wandb/weave/react';
import {constNumber, opIndex} from '@wandb/weave/core';
import {result} from 'lodash';

export const useTraceSpans = (streamId: StreamId, traceId: string): Span[] => {
  const traceSpansNode = useMemo(() => {
    const rowsNode = callsTableNode(streamId);
    const filtered = callsTableFilter(rowsNode, {traceId: traceId});
    return callsTableSelect(filtered);
  }, [streamId, traceId]);
  const traceSpansQuery = useNodeValue(traceSpansNode);

  return useMemo(() => traceSpansQuery.result ?? [], [traceSpansQuery.result]);
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
