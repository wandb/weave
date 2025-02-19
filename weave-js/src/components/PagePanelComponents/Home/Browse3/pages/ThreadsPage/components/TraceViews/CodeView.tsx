import React, {useEffect, useMemo, useState} from 'react';
import styled from 'styled-components';

import {Icon} from '../../../../../../../Icon';
import {TraceViewProps} from '../../types';
import {buildCodeMap, CodeMapNode} from '../../utils';
import {useStackContext} from '../TraceScrubber/context';
import {formatDuration, formatTimestamp, getCallDisplayName} from './utils';

const Container = styled.div`
  height: 100%;
  display: flex;
  flex-direction: column;
  overflow: hidden;
`;

const TreePanel = styled.div`
  height: 50%;
  min-height: 0;
  overflow-y: auto;
  padding: 8px;
  border-bottom: 1px solid #e2e8f0;
  background: #f8fafc;
`;

const NodeContainer = styled.div<{$level: number; $isSelected?: boolean}>`
  margin: 2px 0;
  padding: 8px;
  border: 1px solid ${props => (props.$isSelected ? '#93C5FD' : '#E2e8f0')};
  border-radius: 4px;
  background: ${props => (props.$isSelected ? '#EFF6FF' : 'white')};
  transition: all 0.1s ease-in-out;
  margin-left: 8px;
`;

const NodeHeader = styled.button`
  width: 100%;
  padding: 8px 12px;
  display: flex;
  align-items: center;
  gap: 8px;
  border: none;
  background: none;
  text-align: left;
  cursor: pointer;
  min-height: 32px;
  user-select: none;

  &:hover {
    background: rgba(0, 0, 0, 0.02);
  }
`;

const NodeContent = styled.div<{$isExpanded: boolean}>`
  display: ${props => (props.$isExpanded ? 'flex' : 'none')};
  flex-wrap: wrap;
  gap: 4px;
  
`;

const CallPanel = styled.div`
  height: 50%;
  overflow-y: auto;
  background: #f8fafc;
`;

const CallPanelHeader = styled.div`
  padding: 6px 12px;
  background: #f1f5f9;
  border-bottom: 1px solid #e2e8f0;
  font-size: 11px;
  font-weight: 500;
  color: #64748b;
  display: flex;
  justify-content: space-between;
  align-items: center;
`;

const CallList = styled.div`
  display: flex;
  flex-direction: column;
  gap: 1px;
  padding: 8px;
  background: #f8fafc;
`;

const CallItem = styled.div<{$isSelected?: boolean}>`
  padding: 8px 12px;
  cursor: pointer;
  background: ${props => (props.$isSelected ? '#EFF6FF' : 'white')};
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 8px;
  border: 1px solid ${props => (props.$isSelected ? '#93C5FD' : '#E2e8f0')};
  border-radius: 4px;

  &:hover {
    background: ${props => (props.$isSelected ? '#DBEAFE' : '#F8FAFC')};
  }
`;

const CallInfo = styled.div`
  display: flex;
  align-items: center;
  gap: 16px;
  min-width: 0;
  flex: 1;
`;

const CallName = styled.div`
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 1px;
`;

interface CodeMapNodeProps {
  node: CodeMapNode;
  selectedCallId?: string;
  selectedOpName?: string;
  onCallSelect: (callId: string) => void;
  onOpSelect: (opName: string) => void;
  traceTreeFlat: TraceViewProps['traceTreeFlat'];
  level?: number;
}

const CodeMapNodeComponent: React.FC<CodeMapNodeProps> = ({
  node,
  selectedCallId,
  selectedOpName,
  onCallSelect,
  onOpSelect,
  traceTreeFlat,
  level = 0,
}) => {
  const {setStackState, buildStackForCall} = useStackContext();
  const hasChildren = node.children.length > 0;
  const isSelected = node.opName === selectedOpName;

  // Get duration range and stats for this operation
  const stats = useMemo(() => {
    return node.callIds.reduce(
      (acc, callId) => {
        const call = traceTreeFlat[callId].call;
        const duration = call.ended_at
          ? Date.parse(call.ended_at) - Date.parse(call.started_at)
          : Date.now() - Date.parse(call.started_at);
        return {
          minDuration: Math.min(acc.minDuration, duration),
          maxDuration: Math.max(acc.maxDuration, duration),
          totalDuration: acc.totalDuration + duration,
          errorCount: acc.errorCount + (call.exception ? 1 : 0),
        };
      },
      {
        minDuration: Infinity,
        maxDuration: -Infinity,
        totalDuration: 0,
        errorCount: 0,
      }
    );
  }, [node.callIds, traceTreeFlat]);

  const avgDuration = stats.totalDuration / node.callIds.length;

  const handleClick = (e: React.MouseEvent) => {
    e.preventDefault();
    onOpSelect(node.opName);

    // Select the first call in this operation if we have any calls
    if (node.callIds.length > 0) {
      // Sort calls by start time and select the first one
      const sortedCallIds = [...node.callIds].sort(
        (a, b) =>
          Date.parse(traceTreeFlat[a].call.started_at) -
          Date.parse(traceTreeFlat[b].call.started_at)
      );
      const selectedCall = sortedCallIds[0];
      onCallSelect(selectedCall);

      // Update the stack state for breadcrumbs
      setStackState({
        stack: buildStackForCall(selectedCall),
        originalCallId: selectedCall,
      });
    }
  };

  return (
    <NodeContainer $level={level} $isSelected={isSelected}>
      <NodeHeader onClick={handleClick}>
        <div className="flex min-w-0 flex-1 items-center gap-1">
          <div className="flex min-w-0 flex-col">
            <div className="truncate text-xs font-medium">{node.opName}</div>
            <div className="truncate text-[11px] text-moon-500">
              {node.callIds.length} calls
              {stats.errorCount > 0 && ` • ${stats.errorCount} errors`}
              {` • ${formatDuration(avgDuration)} avg`}
            </div>
          </div>
        </div>
        <div className="whitespace-nowrap text-[11px] text-moon-500">
          {formatDuration(stats.minDuration)} -{' '}
          {formatDuration(stats.maxDuration)}
        </div>
      </NodeHeader>

      {hasChildren && (
        <NodeContent $isExpanded={true}>
          {node.children.map(child => (
            <CodeMapNodeComponent
              key={child.opName}
              node={child}
              selectedCallId={selectedCallId}
              selectedOpName={selectedOpName}
              onCallSelect={onCallSelect}
              onOpSelect={onOpSelect}
              traceTreeFlat={traceTreeFlat}
              level={level + 1}
            />
          ))}
        </NodeContent>
      )}
    </NodeContainer>
  );
};

export const CodeView: React.FC<TraceViewProps> = ({
  traceTreeFlat,
  selectedCallId,
  onCallSelect,
}) => {
  const {setStackState, buildStackForCall} = useStackContext();
  const codeMap = useMemo(() => buildCodeMap(traceTreeFlat), [traceTreeFlat]);
  const [selectedOpName, setSelectedOpName] = useState<string>();

  // Find the selected operation's calls and update when selectedCallId changes
  const selectedOp = useMemo(() => {
    // First try to find the op containing the selected call
    if (selectedCallId) {
      const findOpByCallId = (nodes: CodeMapNode[]): CodeMapNode | null => {
        for (const node of nodes) {
          if (node.callIds.includes(selectedCallId)) {
            return node;
          }
          const found = findOpByCallId(node.children);
          if (found) {
            return found;
          }
        }
        return null;
      };
      const opWithCall = findOpByCallId(codeMap);
      if (opWithCall) {
        return opWithCall;
      }
    }

    // Fall back to currently selected op
    if (!selectedOpName) {
      return null;
    }
    const findOp = (nodes: CodeMapNode[]): CodeMapNode | null => {
      for (const node of nodes) {
        if (node.opName === selectedOpName) {
          return node;
        }
        const found = findOp(node.children);
        if (found) {
          return found;
        }
      }
      return null;
    };
    return findOp(codeMap);
  }, [codeMap, selectedCallId, selectedOpName]);

  // Update selectedOpName when we find the operation containing selectedCallId
  useEffect(() => {
    if (selectedOp && selectedOp.opName !== selectedOpName) {
      setSelectedOpName(selectedOp.opName);
    }
  }, [selectedOp, selectedOpName]);

  // Handle call selection from the call list
  const handleCallSelect = (callId: string) => {
    onCallSelect(callId);
    // Update the stack state for breadcrumbs
    setStackState({
      stack: buildStackForCall(callId),
      originalCallId: callId,
    });
  };

  return (
    <Container>
      <TreePanel>
        {codeMap.map(node => (
          <CodeMapNodeComponent
            key={node.opName}
            node={node}
            selectedCallId={selectedCallId}
            selectedOpName={selectedOpName}
            onCallSelect={onCallSelect}
            onOpSelect={setSelectedOpName}
            traceTreeFlat={traceTreeFlat}
          />
        ))}
      </TreePanel>

      <CallPanel>
        {selectedOp ? (
          <>
            <CallPanelHeader>
              <span>Calls for {selectedOp.opName}</span>
              <span>{selectedOp.callIds.length} calls</span>
            </CallPanelHeader>
            <CallList>
              {selectedOp.callIds.map(callId => {
                const call = traceTreeFlat[callId].call;
                const duration = call.ended_at
                  ? Date.parse(call.ended_at) - Date.parse(call.started_at)
                  : Date.now() - Date.parse(call.started_at);

                return (
                  <CallItem
                    key={callId}
                    $isSelected={callId === selectedCallId}
                    onClick={() => handleCallSelect(callId)}>
                    <CallInfo>
                      <CallName>
                        <div className="truncate text-xs font-medium">
                          {getCallDisplayName(call)}
                        </div>
                        <div className="truncate text-[11px] text-moon-500">
                          {formatTimestamp(call.started_at)}
                        </div>
                      </CallName>
                      <div className="flex items-center gap-2 whitespace-nowrap text-xs">
                        <span className="font-medium">
                          {formatDuration(duration)}
                        </span>
                        {call.exception && (
                          <Icon name="warning" className="text-red-500" />
                        )}
                      </div>
                    </CallInfo>
                  </CallItem>
                );
              })}
            </CallList>
          </>
        ) : (
          <div className="flex h-full items-center justify-center text-moon-500">
            Select an operation to view its calls
          </div>
        )}
      </CallPanel>
    </Container>
  );
};
