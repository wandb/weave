import {useMemo} from 'react';
import {
  StreamId,
  Span,
  callsTableFilter,
  callsTableNode,
  callsTableSelect,
} from './callTree';
import {useNodeValue} from '@wandb/weave/react';

export const useTraceSpans = (streamId: StreamId, traceId: string): Span[] => {
  const traceSpansNode = useMemo(() => {
    const rowsNode = callsTableNode(streamId);
    const filtered = callsTableFilter(rowsNode, {traceId: traceId});
    return callsTableSelect(filtered);
  }, [streamId, traceId]);
  const traceSpansQuery = useNodeValue(traceSpansNode);

  return useMemo(() => traceSpansQuery.result ?? [], [traceSpansQuery.result]);
};
