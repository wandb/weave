import React from 'react';
import styled from 'styled-components';

import {TraceTreeFlat} from '../types';

interface TraceScrubberProps {
  traceTreeFlat: TraceTreeFlat;
  selectedCallId?: string;
  onCallSelect: (callId: string) => void;
}

// Styled components
const Container = styled.div`
  border-top: 1px solid #E2E8F0;
  padding: 8px 16px;
`;

const ScrubberRow = styled.div`
  display: flex;
  align-items: center;
  height: 32px;
  gap: 12px;

  & + & {
    margin-top: 4px;
  }
`;

const Label = styled.div`
  width: 80px;
  font-size: 12px;
  color: #64748B;
  flex-shrink: 0;
`;

const CountIndicator = styled.div`
  width: 60px;
  font-size: 12px;
  color: #64748B;
  flex-shrink: 0;
  text-align: right;
  font-variant-numeric: tabular-nums;
`;

const ScrubberContent = styled.div`
  flex: 1;
  display: flex;
  gap: 12px;
  align-items: center;
`;

interface RangeInputProps {
  $progress: number;
}

const RangeInput = styled.input<RangeInputProps>`
  -webkit-appearance: none;
  width: 100%;
  height: 8px;
  background: linear-gradient(
    to right,
    #3B82F6 0%,
    #3B82F6 ${props => props.$progress}%,
    #E2E8F0 ${props => props.$progress}%,
    #E2E8F0 100%
  );
  border-radius: 4px;
  cursor: pointer;

  &::-webkit-slider-runnable-track {
    width: 100%;
    height: 8px;
    background: transparent;
    border-radius: 4px;
  }

  &::-webkit-slider-thumb {
    -webkit-appearance: none;
    height: 16px;
    width: 16px;
    border-radius: 50%;
    background: #3B82F6;
    border: 2px solid white;
    margin-top: -4px;
    transition: transform 0.1s;
  }

  &::-webkit-slider-thumb:hover {
    transform: scale(1.1);
  }

  &::-moz-range-track {
    width: 100%;
    height: 8px;
    background: transparent;
    border-radius: 4px;
  }

  &::-moz-range-thumb {
    height: 16px;
    width: 16px;
    border-radius: 50%;
    background: #3B82F6;
    border: 2px solid white;
    transition: transform 0.1s;
  }

  &::-moz-range-thumb:hover {
    transform: scale(1.1);
  }

  &:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }
`;

const TooltipContainer = styled.div`
  position: relative;
  display: inline-flex;
  align-items: center;
`;

const TooltipContent = styled.div`
  position: absolute;
  bottom: 100%;
  left: 0;
  margin-bottom: 8px;
  padding: 8px 12px;
  background: #1E293B;
  color: white;
  border-radius: 6px;
  font-size: 12px;
  white-space: nowrap;
  z-index: 10;
  opacity: 0;
  visibility: hidden;
  transition: opacity 0.2s, visibility 0.2s;

  ${TooltipContainer}:hover & {
    opacity: 1;
    visibility: visible;
  }

  &::after {
    content: '';
    position: absolute;
    top: 100%;
    left: 16px;
    border: 6px solid transparent;
    border-top-color: #1E293B;
  }
`;

// Add new styled components for breadcrumbs
const BreadcrumbContainer = styled.div`
  margin-top: 8px;
  padding: 4px 0;
  display: flex;
  align-items: center;
  gap: 4px;
  overflow-x: auto;
  white-space: nowrap;
  font-size: 11px;
  color: #64748B;

  &::-webkit-scrollbar {
    height: 2px;
  }

  &::-webkit-scrollbar-track {
    background: #F1F5F9;
  }

  &::-webkit-scrollbar-thumb {
    background: #CBD5E1;
    border-radius: 1px;
  }
`;

const BreadcrumbItem = styled.button<{$active?: boolean}>`
  padding: 2px 6px;
  border-radius: 4px;
  background: ${props => props.$active ? '#E2E8F0' : 'transparent'};
  color: ${props => props.$active ? '#1E293B' : '#64748B'};
  font-weight: ${props => props.$active ? '500' : '400'};
  cursor: pointer;
  border: none;
  transition: all 0.1s;

  &:hover {
    background: #F1F5F9;
    color: #1E293B;
  }
`;

const BreadcrumbSeparator = styled.span`
  color: #94A3B8;
  user-select: none;
`;

// Common types and utilities
interface BaseScrubberProps {
  traceTreeFlat: TraceTreeFlat;
  selectedCallId?: string;
  onCallSelect: (callId: string) => void;
}

interface ScrubberConfig {
  label: string;
  description: string;
  getNodes: (props: BaseScrubberProps) => string[];
  alwaysEnabled?: boolean;
}

// Add Stack Context
interface StackState {
  stack: string[];
  originalCallId: string | null;
}

interface StackContextType {
  stackState: StackState | null;
  setStackState: (state: StackState | null) => void;
  buildStackForCall: (callId: string) => string[];
}

const StackContext = React.createContext<StackContextType | null>(null);

const useStackContext = () => {
  const context = React.useContext(StackContext);
  if (!context) {
    throw new Error('useStackContext must be used within a StackContextProvider');
  }
  return context;
};

// Create a provider component
const StackContextProvider: React.FC<{
  children: React.ReactNode;
  traceTreeFlat: TraceTreeFlat;
}> = ({children, traceTreeFlat}) => {
  const [stackState, setStackState] = React.useState<StackState | null>(null);

  const buildStackForCall = React.useCallback((callId: string) => {
    const stack: string[] = [];
    let currentId = callId;
    
    // Build stack up to root
    while (currentId) {
      stack.unshift(currentId);
      const node = traceTreeFlat[currentId];
      if (!node) break;
      currentId = node.parentId || '';
    }

    // Build stack down to leaves
    currentId = callId;
    while (currentId) {
      const node = traceTreeFlat[currentId];
      if (!node || node.childrenIds.length === 0) break;
      // Take the first child in chronological order
      const nextId = [...node.childrenIds].sort((a, b) => 
        Date.parse(traceTreeFlat[a].call.started_at) - 
        Date.parse(traceTreeFlat[b].call.started_at)
      )[0];
      stack.push(nextId);
      currentId = nextId;
    }

    return stack;
  }, [traceTreeFlat]);

  const value = React.useMemo(() => ({
    stackState,
    setStackState,
    buildStackForCall,
  }), [stackState, buildStackForCall]);

  return (
    <StackContext.Provider value={value}>
      {children}
    </StackContext.Provider>
  );
};

// Modify the createScrubber to support maintaining state
const createScrubber = ({label, description, getNodes, alwaysEnabled}: ScrubberConfig) => {
  const ScrubberComponent: React.FC<BaseScrubberProps> = (props) => {
    const {selectedCallId, onCallSelect} = props;
    
    // Stack navigation state
    const stackRef = React.useRef<{
      originalCallId: string;
      stack: string[];
    } | null>(null);

    // Get nodes, potentially using the stack reference
    const nodes = React.useMemo(() => {
      // Special case for stack navigation
      if (label === 'Stack') {
        if (!selectedCallId) return [];

        const buildStack = (callId: string) => {
          const stack: string[] = [];
          let currentId = callId;
          
          // Build stack up to root
          while (currentId) {
            stack.unshift(currentId);
            const node = props.traceTreeFlat[currentId];
            if (!node) break;
            currentId = node.parentId || '';
          }

          // Build stack down to leaves
          currentId = callId;
          while (currentId) {
            const node = props.traceTreeFlat[currentId];
            if (!node || node.childrenIds.length === 0) break;
            // Take the first child in chronological order
            const nextId = [...node.childrenIds].sort((a, b) => 
              Date.parse(props.traceTreeFlat[a].call.started_at) - 
              Date.parse(props.traceTreeFlat[b].call.started_at)
            )[0];
            stack.push(nextId);
            currentId = nextId;
          }

          return stack;
        };

        // Only update the stack reference if the selected call changes from outside
        // or if it hasn't been initialized yet
        if (!stackRef.current || !stackRef.current.stack.includes(selectedCallId)) {
          stackRef.current = {
            originalCallId: selectedCallId,
            stack: buildStack(selectedCallId),
          };
        }

        return stackRef.current.stack;
      }

      // Normal case for other scrubbers
      return getNodes(props);
    }, [props, selectedCallId, label]);

    const currentIndex = selectedCallId ? nodes.indexOf(selectedCallId) : 0;
    const progress = nodes.length > 1 
      ? (currentIndex / (nodes.length - 1)) * 100 
      : 0;

    const handleChange = React.useCallback(
      (e: React.ChangeEvent<HTMLInputElement>) => {
        const index = Math.min(
          nodes.length - 1,
          Math.max(0, Math.floor(Number(e.target.value)))
        );
        if (index >= 0 && index < nodes.length) {
          onCallSelect(nodes[index]);
        }
      },
      [onCallSelect, nodes]
    );

    return (
      <ScrubberRow>
        <TooltipContainer>
          <Label>{label}</Label>
          <TooltipContent>{description}</TooltipContent>
        </TooltipContainer>
        <ScrubberContent>
          <RangeInput
            type="range"
            min={0}
            max={Math.max(0, nodes.length - 1)}
            value={currentIndex}
            onChange={handleChange}
            $progress={progress}
            disabled={!alwaysEnabled && nodes.length <= 1}
          />
          <CountIndicator>
            {nodes.length > 0 ? `${currentIndex + 1}/${nodes.length}` : '0/0'}
          </CountIndicator>
        </ScrubberContent>
      </ScrubberRow>
    );
  };

  return React.memo(ScrubberComponent);
};

// Scrubber implementations
const TimelineScrubber = createScrubber({
  label: 'Timeline',
  description: 'Navigate through all calls in chronological order',
  alwaysEnabled: true,
  getNodes: ({traceTreeFlat}) => 
    Object.values(traceTreeFlat)
      .sort((a, b) => Date.parse(a.call.started_at) - Date.parse(b.call.started_at))
      .map(node => node.id),
});

const PeerScrubber = createScrubber({
  label: 'Peers',
  description: 'Navigate through all calls with the same op as the selected call',
  getNodes: ({traceTreeFlat, selectedCallId}) => {
    if (!selectedCallId) return [];
    const currentNode = traceTreeFlat[selectedCallId];
    if (!currentNode) return [];
    
    return Object.values(traceTreeFlat)
      .filter(node => node.call.op_name === currentNode.call.op_name)
      .sort((a, b) => Date.parse(a.call.started_at) - Date.parse(b.call.started_at))
      .map(node => node.id);
  },
});

const SiblingScrubber = createScrubber({
  label: 'Siblings',
  description: 'Navigate through calls that share the same parent as the selected call',
  getNodes: ({traceTreeFlat, selectedCallId}) => {
    if (!selectedCallId) return [];
    const currentNode = traceTreeFlat[selectedCallId];
    if (!currentNode) return [];
    const parentId = currentNode.parentId;
    
    if (!parentId) {
      return Object.values(traceTreeFlat)
        .filter(node => !node.parentId)
        .sort((a, b) => Date.parse(a.call.started_at) - Date.parse(b.call.started_at))
        .map(node => node.id);
    }

    return traceTreeFlat[parentId].childrenIds;
  },
});

// Create a separate component for the stack scrubber to properly use hooks
const StackScrubberContent: React.FC<BaseScrubberProps> = (props) => {
  const {selectedCallId} = props;
  const {stackState, setStackState, buildStackForCall} = useStackContext();
  
  React.useEffect(() => {
    if (!selectedCallId) {
      setStackState(null);
      return;
    }

    // Only update stack state if we don't have one or if the selected call
    // isn't in our current stack
    if (!stackState || !stackState.stack.includes(selectedCallId)) {
      setStackState({
        originalCallId: selectedCallId,
        stack: buildStackForCall(selectedCallId),
      });
    }
  }, [selectedCallId, stackState, setStackState, buildStackForCall]);

  return (
    <ScrubberRow>
      <TooltipContainer>
        <Label>Stack</Label>
        <TooltipContent>Navigate up and down the call stack from root to the selected call</TooltipContent>
      </TooltipContainer>
      <ScrubberContent>
        <RangeInput
          type="range"
          min={0}
          max={Math.max(0, (stackState?.stack.length || 1) - 1)}
          value={stackState?.stack.indexOf(selectedCallId || '') || 0}
          onChange={(e) => {
            const index = Math.min(
              (stackState?.stack.length || 1) - 1,
              Math.max(0, Math.floor(Number(e.target.value)))
            );
            if (stackState?.stack[index]) {
              props.onCallSelect(stackState.stack[index]);
            }
          }}
          $progress={stackState?.stack.length ? 
            ((stackState.stack.indexOf(selectedCallId || '') || 0) / (stackState.stack.length - 1)) * 100 
            : 0}
          disabled={!stackState?.stack.length || stackState.stack.length <= 1}
        />
        <CountIndicator>
          {stackState?.stack.length ? 
            `${(stackState.stack.indexOf(selectedCallId || '') || 0) + 1}/${stackState.stack.length}` 
            : '0/0'}
        </CountIndicator>
      </ScrubberContent>
    </ScrubberRow>
  );
};

// Simplify the StackScrubber to just render the content component
const StackScrubber: React.FC<BaseScrubberProps> = (props) => {
  return <StackScrubberContent {...props} />;
};

// Modify the StackBreadcrumb to use context
const StackBreadcrumb: React.FC<BaseScrubberProps> = ({
  traceTreeFlat,
  selectedCallId,
  onCallSelect,
}) => {
  const {stackState} = useStackContext();
  
  if (!selectedCallId || !stackState) return null;

  const stack = stackState.stack.map(id => ({
    id,
    name: traceTreeFlat[id]?.call.display_name || 
          traceTreeFlat[id]?.call.op_name.split('/').pop() || 
          id,
  }));

  if (stack.length <= 1) return null;

  return (
    <BreadcrumbContainer>
      {stack.map((node, index) => (
        <React.Fragment key={node.id}>
          {index > 0 && <BreadcrumbSeparator>/</BreadcrumbSeparator>}
          <BreadcrumbItem
            $active={node.id === selectedCallId}
            onClick={() => onCallSelect(node.id)}
            title={node.name}>
            {node.name}
          </BreadcrumbItem>
        </React.Fragment>
      ))}
    </BreadcrumbContainer>
  );
};

// Modify the main TraceScrubber component to include the context provider
export const TraceScrubber: React.FC<TraceScrubberProps> = (props) => {
  return (
    <StackContextProvider traceTreeFlat={props.traceTreeFlat}>
      <Container>
        <TimelineScrubber {...props} />
        <PeerScrubber {...props} />
        <SiblingScrubber {...props} />
        <StackScrubber {...props} />
        <StackBreadcrumb {...props} />
      </Container>
    </StackContextProvider>
  );
}; 