import {TraceCallSchema} from '../wfReactInterface/traceServerClientTypes';

/**
 * Props for the ThreadsPage component
 */
export interface ThreadsPageProps {
  /** The entity (organization/user) context */
  entity: string;
  /** The project context */
  project: string;
  /** Optional initial thread ID to select */
  threadId?: string;
}

/**
 * Flattened representation of a trace call tree
 */
export interface TraceTreeFlat {
  [callId: string]: {
    /** The unique identifier for this call */
    id: string;
    /** The parent call ID, if any */
    parentId?: string;
    /** IDs of child calls */
    childrenIds: string[];
    /** Order in depth-first traversal */
    dfsOrder: number;
    /** The actual call data */
    call: TraceCallSchema;
  };
}

/**
 * Props shared by all thread view components
 */
export interface ThreadViewProps {
  /** Callback when a trace is selected */
  onTraceSelect: (traceId: string) => void;
  /** Available traces for the thread */
  traceRoots: TraceCallSchema[];
  /** Currently selected trace ID */
  selectedTraceId?: string;
  /** Whether traces are currently loading */
  loading: boolean;
  /** Error loading traces, if any */
  error: Error | null;
}

/**
 * Props shared by all trace view components
 */
export interface TraceViewProps {
  /** The flattened trace call tree */
  traceTreeFlat: TraceTreeFlat;
  /** Currently selected call ID */
  selectedCallId?: string;
  /** Callback when a call is selected */
  onCallSelect: (callId: string) => void;
}
