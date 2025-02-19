import {TraceTreeFlat} from '../../types';

export interface BaseScrubberProps {
  traceTreeFlat: TraceTreeFlat;
  selectedCallId?: string;
  onCallSelect: (callId: string) => void;
}

export interface ScrubberConfig {
  label: string;
  description: string;
  getNodes: (props: BaseScrubberProps) => string[];
  alwaysEnabled?: boolean;
}

export interface StackState {
  stack: string[];
  originalCallId: string | null;
}

export interface StackContextType {
  stackState: StackState | null;
  setStackState: (state: StackState | null) => void;
  buildStackForCall: (callId: string) => string[];
} 