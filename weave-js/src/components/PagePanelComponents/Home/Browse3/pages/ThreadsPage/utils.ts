import {TraceCallSchema} from '../wfReactInterface/traceServerClientTypes';
import {TraceTreeFlat} from './types';

export const buildTraceTreeFlat = (
  traceCalls: TraceCallSchema[]
): TraceTreeFlat => {
  const traceTreeFlat: TraceTreeFlat = {};
  traceCalls.forEach(call => {
    traceTreeFlat[call.id] = {
      id: call.id,
      parentId: call.parent_id,
      childrenIds: [],
      dfsOrder: 0,
      call,
    };
  });
  traceCalls.forEach(call => {
    if (call.parent_id) {
      traceTreeFlat[call.parent_id].childrenIds.push(call.id);
    }
  });
  const sortFn = (a: string, b: string) => {
    const aCall = traceTreeFlat[a];
    const bCall = traceTreeFlat[b];
    const aStartedAt = Date.parse(aCall.call.started_at);
    const bStartedAt = Date.parse(bCall.call.started_at);
    return aStartedAt - bStartedAt;
  };
  // Sort the children calls by start time
  Object.values(traceTreeFlat).forEach(call => {
    call.childrenIds.sort(sortFn);
  });
  let dfsOrder = 0;
  let stack: string[] = [];
  Object.values(traceTreeFlat).forEach(call => {
    if (call.parentId === null) {
      stack.push(call.id);
    }
  });
  stack.sort(sortFn);
  while (stack.length > 0) {
    const callId = stack.shift();
    if (!callId) {
      continue;
    }
    const call = traceTreeFlat[callId];
    if (call) {
      call.dfsOrder = dfsOrder;
      dfsOrder++;
    }
    stack = [...call.childrenIds, ...stack];
  }
  return traceTreeFlat;
};
