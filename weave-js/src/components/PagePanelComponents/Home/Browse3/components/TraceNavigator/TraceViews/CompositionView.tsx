import * as Colors from '@wandb/weave/common/css/color.styles';
import React, {useMemo} from 'react';
import styled from 'styled-components';

import TraceScrubber from '../TraceScrubber';
import {TreeView} from './TreeView';
import {TraceViewProps} from './types';
import {
  buildCodeCompositionMap,
  CodeCompositionMapNode,
  formatDuration,
  getSortedPeerPathCallIds,
  locateNodeForCallId,
} from './utils';
const Container = styled.div`
  height: 100%;
  display: flex;
  flex-direction: column;
  overflow: hidden;
`;
Container.displayName = 'Container';

const TreePanel = styled.div`
  height: 50%;
  min-height: 0;
  overflow-y: auto;
  padding: 8px;
  border-bottom: 1px solid ${Colors.MOON_200};
  background: ${Colors.MOON_100};
`;
TreePanel.displayName = 'TreePanel';

const NodeContainer = styled.div<{$level: number; $isSelected?: boolean}>`
  margin: 2px 0;
  padding: 8px;
  border: 1px solid
    ${props => (props.$isSelected ? Colors.TEAL_500 : Colors.MOON_200)};
  border-radius: 4px;
  background: ${props => (props.$isSelected ? Colors.MOON_100 : Colors.WHITE)};
  transition: all 0.1s ease-in-out;
  flex: 1 1 100px;
`;
NodeContainer.displayName = 'NodeContainer';

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
NodeHeader.displayName = 'NodeHeader';

const NodeContent = styled.div<{$isExpanded: boolean}>`
  display: ${props => (props.$isExpanded ? 'flex' : 'none')};
  flex-wrap: wrap;
  gap: 4px;
`;
NodeContent.displayName = 'NodeContent';

const CallPanel = styled.div`
  height: 50%;
  overflow-y: auto;
  background: ${Colors.MOON_100};
  display: flex;
  flex-direction: column;
`;
CallPanel.displayName = 'CallPanel';

const CallPanelHeader = styled.div`
  padding: 6px 12px;
  background: ${Colors.MOON_100};
  border-bottom: 1px solid ${Colors.MOON_200};
  font-size: 11px;
  font-weight: 500;
  color: ${Colors.MOON_500};
  display: flex;
  justify-content: space-between;
  align-items: center;
`;
CallPanelHeader.displayName = 'CallPanelHeader';

const RecursionBlock = styled.div`
  margin: 2px 0;
  padding: 8px 12px;
  border: 1px dashed ${Colors.TEAL_500};
  border-radius: 4px;
  background: ${Colors.MOON_100};
  color: ${Colors.TEAL_500};
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
RecursionBlock.displayName = 'RecursionBlock';

interface CodeMapNodeProps extends TraceViewProps {
  node: CodeCompositionMapNode;
  level?: number;
}

const CodeMapNodeComponent: React.FC<CodeMapNodeProps> = ({
  node,
  focusedCallId: selectedCallId,
  setFocusedCallId: onCallSelect,
  traceTreeFlat,
  stack,
  setRootCallId,
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
            ? stats.minDuration === stats.maxDuration
              ? formatDuration(stats.minDuration)
              : `${formatDuration(stats.minDuration)} - ${formatDuration(
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
              focusedCallId={selectedCallId}
              setFocusedCallId={onCallSelect}
              traceTreeFlat={traceTreeFlat}
              stack={stack}
              level={level + 1}
              setRootCallId={setRootCallId}
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

export const CompositionView: React.FC<TraceViewProps> = props => {
  const {
    traceTreeFlat,
    focusedCallId: selectedCallId,
    setFocusedCallId: onCallSelect,
    stack,
  } = props;
  const codeMap = useMemo(
    () => buildCodeCompositionMap(traceTreeFlat),
    [traceTreeFlat]
  );

  // Find the selected operation's calls and update when selectedCallId changes
  const selectedCodeNode = useMemo(() => {
    // First try to find the op containing the selected call
    if (!selectedCallId) {
      return null;
    }
    return locateNodeForCallId(codeMap, selectedCallId);
  }, [codeMap, selectedCallId]);

  const selectedPeerPathCallIds = useMemo(() => {
    return getSortedPeerPathCallIds(selectedCodeNode, traceTreeFlat);
  }, [selectedCodeNode, traceTreeFlat]);
  return (
    <Container>
      <TreePanel>
        {codeMap.map(node => (
          <CodeMapNodeComponent
            key={node.opName}
            node={node}
            focusedCallId={selectedCallId}
            setFocusedCallId={onCallSelect}
            traceTreeFlat={traceTreeFlat}
            stack={stack}
            setRootCallId={props.setRootCallId}
          />
        ))}
      </TreePanel>

      <CallPanel>
        {selectedCodeNode ? (
          <>
            <CallPanelHeader>
              <span>Calls for {selectedCodeNode.opName}</span>
              <span>{selectedPeerPathCallIds.length} calls</span>
            </CallPanelHeader>

            <div className="flex-1 overflow-hidden">
              <TreeView
                traceTreeFlat={traceTreeFlat}
                focusedCallId={selectedCallId}
                setFocusedCallId={onCallSelect}
                filterCallIds={selectedPeerPathCallIds}
                stack={stack}
                setRootCallId={props.setRootCallId}
              />
            </div>
          </>
        ) : (
          <div className="flex h-full items-center justify-center text-moon-500">
            Select an operation to view its calls
          </div>
        )}
      </CallPanel>
      <TraceScrubber {...props} allowedScrubbers={['codePath']} />
    </Container>
  );
};
