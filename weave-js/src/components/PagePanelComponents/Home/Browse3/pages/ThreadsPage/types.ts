import {TraceCallSchema} from '../wfReactInterface/traceServerClientTypes';

export type ThreadsPageProps = {
  entity: string;
  project: string;
  threadId?: string;
};

export type TraceTreeFlat = {
  [callId: string]: {
    id: string;
    parentId?: string;
    childrenIds: string[];
    dfsOrder: number;
    call: TraceCallSchema;
  };
};

export type ThreadViewType = 'list' | 'timeline';
export type TraceViewType = 'timeline' | 'tree' | 'table' | 'list';
