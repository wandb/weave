import React, {useEffect, useMemo, useState} from 'react';
import styled from 'styled-components';

import {TreeView} from './TreeView';
import {TraceViewProps} from './types';
import {buildCodeMap, CodeMapNode} from './utils';
import {formatDuration} from './utils';

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
  flex: 1 1 100px;
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
  background: #f8fafc;
  border-bottom: 1px solid #e2e8f0;
  font-size: 11px;
  font-weight: 500;
  color: #64748b;
  display: flex;
  justify-content: space-between;
  align-items: center;
`;

const RecursionBlock = styled.div`
  margin: 2px 0;
  padding: 8px 12px;
  border: 1px dashed #6366f1;
  border-radius: 4px;
  background: #f8fafc;
  color: #6366f1;
  font-size: 14px;
  display: flex;
  align-items: center;
  gap: 4px;
  cursor: default;
  flex: 1 1 100px;

  &::before {
    content: '↺';
    font-weight: bold;
  }
`;

interface CodeMapNodeProps extends TraceViewProps {
  node: CodeMapNode;
  selectedOpName?: string;
  onCallSelect: (callId: string) => void;
  onOpSelect: (opName: string) => void;
  level?: number;
}

const CodeMapNodeComponent: React.FC<CodeMapNodeProps> = ({
  node,
  selectedCallId,
  selectedOpName,
  onCallSelect,
  onOpSelect,
  traceTreeFlat,
  stack,
  level = 0,
}) => {
  const hasChildren = node.children.length > 0;
  const isSelected = node.callIds.includes(selectedCallId ?? '');
  const recursiveAncestors = Array.from(node.recursiveAncestors);

  // Get duration range and stats for this operation
  const stats = useMemo(() => {
    const initialStats = {
      minDuration: Infinity,
      maxDuration: -Infinity,
      totalDuration: 0,
      errorCount: 0,
      finishedCallCount: 0,
      unfinishedCallCount: 0,
    };

    return node.callIds.reduce((acc, callId) => {
      const call = traceTreeFlat[callId].call;

      // Track errors regardless of completion status
      if (call.exception) {
        acc.errorCount++;
      }

      // Only include finished calls in timing calculations
      if (call.ended_at) {
        const duration =
          Date.parse(call.ended_at) - Date.parse(call.started_at);
        acc.minDuration = Math.min(acc.minDuration, duration);
        acc.maxDuration = Math.max(acc.maxDuration, duration);
        acc.totalDuration += duration;
        acc.finishedCallCount++;
      } else {
        acc.unfinishedCallCount++;
      }

      return acc;
    }, initialStats);
  }, [node.callIds, traceTreeFlat]);

  // Only calculate average if we have finished calls
  const avgDuration =
    stats.finishedCallCount > 0
      ? stats.totalDuration / stats.finishedCallCount
      : 0;

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
    }
  };

  return (
    <NodeContainer $level={level} $isSelected={isSelected}>
      <NodeHeader onClick={handleClick}>
        <div className="flex min-w-0 flex-1 items-center gap-1">
          <div className="flex min-w-0 flex-col">
            <div className="flex items-center truncate text-sm font-medium">
              {node.opName}
            </div>
            <div className="truncate text-[11px] text-moon-500">
              {stats.finishedCallCount} finished
              {stats.unfinishedCallCount > 0 &&
                ` • ${stats.unfinishedCallCount} running`}
              {stats.errorCount > 0 && ` • ${stats.errorCount} errors`}
              {stats.finishedCallCount > 0 &&
                ` • ${formatDuration(avgDuration)} avg`}
            </div>
          </div>
        </div>
        <div className="whitespace-nowrap text-[11px] text-moon-500">
          {stats.finishedCallCount > 0
            ? `${formatDuration(stats.minDuration)} - ${formatDuration(
                stats.maxDuration
              )}`
            : 'Running...'}
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
              stack={stack}
              level={level + 1}
            />
          ))}
        </NodeContent>
      )}
      {recursiveAncestors.map(ancestor => (
        <RecursionBlock key={ancestor}>{ancestor}</RecursionBlock>
      ))}
    </NodeContainer>
  );
};

export const CodeView: React.FC<TraceViewProps> = ({
  traceTreeFlat,
  selectedCallId,
  onCallSelect,
  stack,
}) => {
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
            stack={stack}
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

            <div className="flex-1 overflow-hidden">
              <TreeView
                traceTreeFlat={traceTreeFlat}
                selectedCallId={selectedCallId}
                onCallSelect={onCallSelect}
                filterCallIds={selectedOp.callIds}
                stack={stack}
              />
            </div>
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
