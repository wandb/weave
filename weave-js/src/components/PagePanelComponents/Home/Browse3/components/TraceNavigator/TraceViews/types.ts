import {TraceCallSchema} from '../../../pages/wfReactInterface/traceServerClientTypes';

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
    /** Whether this call has a descendant that has errors */
    descendantHasErrors: boolean;
  };
}

export type StackState = string[];

/**
 * Props shared by all trace view components
 */
export interface TraceViewProps {
  /** The flattened trace call tree */
  traceTreeFlat: TraceTreeFlat;
  /** Currently selected call ID */
  focusedCallId?: string;
  /** The root call ID */
  rootCallId?: string;
  /** Current stack  */
  stack: StackState;
  /** Callback when a call is selected */
  setFocusedCallId: (callId: string) => void;
  /** Callback when a call is selected */
  setRootCallId: (callId: string) => void;
}
