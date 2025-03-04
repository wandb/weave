import {TraceCallSchema} from '../wfReactInterface/traceServerClientTypes';
import {CallSchema} from '../wfReactInterface/wfDataModelHooksInterface';

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
  /** Callback when a thread is selected */
  onThreadSelect?: (threadId: string) => void;
  /** Polling interval in milliseconds (0 for no polling) */
  pollIntervalMs?: number;
}

/**
 * Props shared by all call view components
 */
export interface CallViewProps {
  /** The loaded call data */
  call: CallSchema;
}
