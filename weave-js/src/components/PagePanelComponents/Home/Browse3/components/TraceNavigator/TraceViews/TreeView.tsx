import {Button} from '@wandb/weave/components/Button';
import {Icon, IconName} from '@wandb/weave/components/Icon';
import {useScrollIntoView} from '@wandb/weave/components/PagePanelComponents/Home/Browse3/hooks/scrollIntoView';
import React, {useEffect, useMemo} from 'react';

import {TraceCallSchema} from '../../../pages/wfReactInterface/traceServerClientTypes';
import {parseSpanName} from '../../../pages/wfReactInterface/tsDataModelHooks';
import {TraceViewProps} from './types';
import {formatDuration, getCallDisplayName, getColorForOpName} from './utils';

interface TreeNodeProps {
  id: string;
  call: TraceCallSchema;
  childrenIds: string[];
  traceTreeFlat: TraceViewProps['traceTreeFlat'];
  selectedCallId?: string;
  onCallSelect: (id: string) => void;
  level?: number;
  filterCallIds?: Set<string>;
}

// Status type for the node
type NodeStatus = 'success' | 'running' | 'error' | 'unknown';

// Helper function to get status color
const getStatusColor = (status: NodeStatus) => {
  switch (status) {
    case 'success':
      return 'bg-green-500';
    case 'running':
      return 'bg-yellow-500';
    case 'error':
      return 'bg-red-500';
    default:
      return 'bg-moon-500';
  }
};

type NodeType = 'agent' | 'tool' | 'llm' | 'model' | 'evaluation' | 'none';

// Helper function to get call type icon
const getCallTypeIcon = (type: NodeType): IconName => {
  switch (type) {
    case 'agent':
      return 'robot-service-member';
    case 'tool':
      return 'code-alt';
    case 'llm':
      return 'forum-chat-bubble';
    case 'none':
      return 'circle';
    case 'model':
      return 'model';
    case 'evaluation':
      return 'number';
    default:
      return 'circle';
  }
};

const spanNameToTypeHeuristic = (spanName: string): NodeType => {
  spanName = spanName.toLowerCase();
  if (spanName.includes('agent')) {
    return 'agent';
  }
  if (spanName.includes('tool')) {
    return 'tool';
  }
  if (
    spanName.includes('completion') ||
    spanName.includes('generation') ||
    spanName.includes('chat') ||
    spanName.includes('llm')
  ) {
    return 'llm';
  }
  if (
    spanName.includes('model') ||
    spanName.includes('predict') ||
    spanName.includes('generate')
  ) {
    return 'model';
  }
  if (spanName.includes('evaluation')) {
    return 'evaluation';
  }
  return 'none';
};

const getStatus = (call: TraceCallSchema): NodeStatus => {
  if (call.exception) {
    return 'error';
  }
  if (call.ended_at) {
    return 'success';
  }
  if (Date.now() - Date.parse(call.started_at) > 1000 * 60 * 60 * 24) {
    return 'unknown';
  }
  return 'running';
};

const TreeNode: React.FC<TreeNodeProps> = ({
  id,
  call,
  childrenIds,
  traceTreeFlat,
  selectedCallId,
  onCallSelect,
  level = 0,
  filterCallIds,
}) => {
  const nodeRef = React.useRef<HTMLDivElement>(null);
  const [isExpanded, setIsExpanded] = React.useState(true);
  const duration = call.ended_at
    ? Date.parse(call.ended_at) - Date.parse(call.started_at)
    : null;

  const status: NodeStatus = getStatus(call);
  // Derive type from the op_name as a fallback
  const spanName = parseSpanName(call.op_name);
  const typeName = spanNameToTypeHeuristic(spanName);
  const cost = 0.0348;
  const tokens = 12377;

  const opColor = getColorForOpName(spanName);
  const chevronIcon: IconName = isExpanded ? 'chevron-down' : 'chevron-next';

  // Auto-expand when filtering
  useEffect(() => {
    if (filterCallIds) {
      setIsExpanded(true);
    }
  }, [filterCallIds]);

  useScrollIntoView(nodeRef, id === selectedCallId);

  // If filtering is active and this node is not in the filter, don't show it
  if (filterCallIds && !filterCallIds.has(id)) {
    return null;
  }

  // Filter child IDs to only those in the filter (if filtering is active)
  const filteredChildrenIds = filterCallIds
    ? childrenIds.filter(childId => filterCallIds.has(childId))
    : childrenIds;

  const hasChildren = filteredChildrenIds.length > 0;
  return (
    <div className="flex flex-col">
      <span ref={nodeRef} className="w-full px-4">
        <Button
          variant={id === selectedCallId ? 'secondary' : 'ghost'}
          active={id === selectedCallId}
          onClick={() => onCallSelect(id)}
          className="w-full justify-start px-8 text-left"
          style={{
            borderLeft: `4px solid ${opColor}`,
          }}>
          <div className="flex w-full items-center justify-between">
            {/* Left section with indentation, chevron, status, type icon, and name */}
            <div className="flex min-w-0 flex-1 items-center">
              <div style={{width: level * 24}} />
              {hasChildren ? (
                <Icon
                  name={chevronIcon}
                  size="small"
                  onClick={(e: React.MouseEvent) => {
                    e.stopPropagation();
                    setIsExpanded(!isExpanded);
                  }}
                  className="p-0.5 shrink-0 cursor-pointer rounded hover:bg-moon-200"
                />
              ) : (
                <div className="w-4" />
              )}
              <Icon
                name={getCallTypeIcon(typeName)}
                size="small"
                className="mx-1 shrink-0 text-moon-500"
              />
              <div className="ml-2 truncate font-medium">
                {getCallDisplayName(call)}
              </div>
            </div>

            {/* Right section with metrics */}
            <div className="ml-8 flex shrink-0 items-center gap-8 text-sm text-moon-500">
              <div
                className={`h-8 w-8 rounded-full ${getStatusColor(status)}`}
              />
              <div className="w-48 text-right">
                {duration !== null ? formatDuration(duration) : ''}
              </div>
              <div className="w-48 text-right">${cost.toFixed(4)}</div>
              <div className="w-48 text-right">{tokens.toLocaleString()}</div>
            </div>
          </div>
        </Button>
      </span>
      {isExpanded && hasChildren && (
        <div className="flex flex-col">
          {filteredChildrenIds.map(childId => {
            const child = traceTreeFlat[childId];
            return (
              <TreeNode
                key={childId}
                id={childId}
                call={child.call}
                childrenIds={child.childrenIds}
                traceTreeFlat={traceTreeFlat}
                selectedCallId={selectedCallId}
                onCallSelect={onCallSelect}
                level={level + 1}
                filterCallIds={filterCallIds}
              />
            );
          })}
        </div>
      )}
    </div>
  );
};

export const TreeView: React.FC<
  TraceViewProps & {filterCallIds?: string[]}
> = ({traceTreeFlat, selectedCallId, onCallSelect, filterCallIds}) => {
  const filterSet = useMemo(
    () => (filterCallIds ? new Set(filterCallIds) : undefined),
    [filterCallIds]
  );

  const rootNodes = useMemo(() => {
    if (!filterCallIds || filterCallIds.length === 0) {
      // No filtering - show the normal tree with root nodes
      return Object.values(traceTreeFlat).filter(
        node => !node.parentId || !traceTreeFlat[node.parentId]
      );
    }

    // When filtering, we only want to show nodes that are in the filter
    const filterIdSet = new Set(filterCallIds);

    // Create a special set of "root" nodes for the filtered view
    // These are nodes that are in the filter but don't have parents in the filter
    const filteredRootNodes = Object.values(traceTreeFlat).filter(node => {
      if (!filterIdSet.has(node.id)) {
        return false; // Node not in filter
      }

      // Check if this node has a parent that's also in the filter
      return (
        !node.parentId ||
        !traceTreeFlat[node.parentId] ||
        !filterIdSet.has(node.parentId)
      );
    });

    return filteredRootNodes;
  }, [traceTreeFlat, filterCallIds]);

  return (
    <div className="h-full overflow-hidden">
      <div className="h-[calc(100%)] overflow-y-auto pb-4 pt-4">
        <div className="flex flex-col">
          {rootNodes.map(node => (
            <TreeNode
              key={node.id}
              id={node.id}
              call={node.call}
              childrenIds={node.childrenIds}
              traceTreeFlat={traceTreeFlat}
              selectedCallId={selectedCallId}
              onCallSelect={onCallSelect}
              filterCallIds={filterSet}
            />
          ))}
        </div>
      </div>
    </div>
  );
};
