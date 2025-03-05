import {Button} from '@wandb/weave/components/Button';
import {Select} from '@wandb/weave/components/Form/Select';
import {TextField} from '@wandb/weave/components/Form/TextField';
import {Icon, IconName} from '@wandb/weave/components/Icon';
import {useScrollIntoView} from '@wandb/weave/components/PagePanelComponents/Home/Browse3/hooks/scrollIntoView';
import * as Switch from '@wandb/weave/components/Switch';
import {
  getTagColorClass,
  IconOnlyPill,
  TagColorName,
} from '@wandb/weave/components/Tag';
import {Tooltip} from '@wandb/weave/components/Tooltip';
import React, {ReactNode,useEffect, useMemo, useRef, useState} from 'react';

import {STATUS_INFO, StatusChip} from '../../../pages/common/StatusChip';
import {TraceCallSchema} from '../../../pages/wfReactInterface/traceServerClientTypes';
import {
  parseSpanName,
  traceCallStatusCode,
} from '../../../pages/wfReactInterface/tsDataModelHooks';
import {TraceViewProps} from './types';
import {formatDuration, getCallDisplayName, getColorForOpName} from './utils';

// Width breakpoints
const WIDTH_BREAKPOINTS = {
  COMPACT: 250,
  MEDIUM: 300,
  LARGE: 350,
};

// Hook to track container width
const useContainerWidth = () => {
  const containerRef = useRef<HTMLDivElement>(null);
  const [width, setWidth] = useState(0);

  useEffect(() => {
    if (!containerRef.current) {
      return;
    }

    const updateWidth = () => {
      if (containerRef.current) {
        setWidth(containerRef.current.offsetWidth);
      }
    };

    const resizeObserver = new ResizeObserver(updateWidth);
    resizeObserver.observe(containerRef.current);
    updateWidth(); // Initial measurement

    return () => resizeObserver.disconnect();
  }, []);

  return {containerRef, width};
};

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

const opTypeToColor = (typeName: NodeType): TagColorName => {
  switch (typeName) {
    case 'agent':
      return 'blue';
    case 'tool':
      return 'gold';
    case 'llm':
      return 'purple';
    case 'model':
      return 'green';
    case 'evaluation':
      return 'cactus';
    default:
      return 'moon';
  }
};

// Note to future dev: this should probably be configurable at the database / attribute level
// for now we use these simple heuristics but this can be improved
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
    spanName.includes('generate') ||
    spanName.includes('invoke')
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

const TreeNode: React.FC<TreeNodeProps & {containerWidth: number, deemphasizeCallIds?: string[]}> = ({
  id,
  call,
  childrenIds,
  traceTreeFlat,
  selectedCallId,
  onCallSelect,
  level = 0,
  filterCallIds,
  deemphasizeCallIds,
  containerWidth,
}) => {
  const nodeRef = React.useRef<HTMLDivElement>(null);
  const [isExpanded, setIsExpanded] = React.useState(true);
  const duration = call.ended_at
    ? Date.parse(call.ended_at) - Date.parse(call.started_at)
    : null;

  const status: NodeStatus = getStatus(call);
  const spanName = parseSpanName(call.op_name);
  const typeName = spanNameToTypeHeuristic(spanName);
  const cost = 0.0348;
  const tokens = 12377;

  const opTypeColor = opTypeToColor(typeName);
  const chevronIcon: IconName = isExpanded ? 'chevron-down' : 'chevron-next';
  const isDeemphasized = deemphasizeCallIds?.includes(id);

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
  const statusCode = traceCallStatusCode(call);

  const showTypeIcon = containerWidth >= WIDTH_BREAKPOINTS.LARGE;
  const showDuration = containerWidth >= WIDTH_BREAKPOINTS.MEDIUM;
  const showStatusIcon = containerWidth >= WIDTH_BREAKPOINTS.COMPACT;
  const indentMultiplier = Math.max(4, Math.min(32, containerWidth / 50));

  return (
    <div className="flex flex-col">
      <span ref={nodeRef} className="w-full px-4">
        <Button
          variant={id === selectedCallId ? 'secondary' : 'ghost'}
          active={id === selectedCallId}
          onClick={() => onCallSelect(id)}
          className="w-full justify-start px-8 text-left text-sm h-[32px] " 
          style={
            {
              opacity: isDeemphasized ? 0.6 : 1,
              // borderLeft: `4px solid ${opColor}`,
            }
          }>
          <div className="flex w-full items-center justify-between gap-8">
            <div className="flex-0 flex min-w-0 items-center">
              {showTypeIcon ? (
                <IconOnlyPill
                  icon={getCallTypeIcon(typeName)}
                  color={opTypeColor}
                  isInteractive={false}
                />
              ) : (
                <div
                  className={`h-8 w-8 rounded-full ${getTagColorClass(
                    opTypeColor
                  )}`}
                />
              )}
            </div>
            {/* Left section with indentation, chevron, status, type icon, and name */}
            <div className="flex min-w-0 flex-1 items-center">
              <div style={{minWidth: level * indentMultiplier}} />
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

              {/* <Icon
                name={getCallTypeIcon(typeName)}
                size="small"
                className="mx-1 shrink-0 text-moon-500"
                style={{backgroundColor: opColor, borderRadius: '50%'}}
              /> */}

              <div className="ml-2 truncate font-medium">
              {getCallDisplayName(call)}
              </div>
            </div>

            {/* Right section with metrics */}
            <div className="ml-8 flex shrink-0 items-center gap-8 text-xs text-moon-400">
              {showDuration && (
                <div className="w-48 text-right">
                  {duration !== null ? formatDuration(duration) : ''}
                </div>
              )}
              {/* <div
                className={`h-8 w-8 rounded-full ${getTagColorClass(STATUS_INFO[statusCode].color)}`}
              /> */}
              {/* <div style={{width: '22px', height: '22px', overflow: 'hidden'}}> */}
              {/* <div className="w-22 text-right"> */}
              {showStatusIcon ? (
                <StatusChip value={statusCode} iconOnly />
              ) : (
                <div
                  className={`h-8 w-8 rounded-full ${getTagColorClass(
                    STATUS_INFO[statusCode].color
                  )}`}
                />
              )}

              {/* </div> */}
              {/* <div className="w-48 text-right">${cost.toFixed(4)}</div>
              <div className="w-48 text-right">{tokens.toLocaleString()}</div> */}
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
                containerWidth={containerWidth}
                deemphasizeCallIds={deemphasizeCallIds}
              />
            );
          })}
        </div>
      )}
    </div>
  );
};

type ExtendedNodeType = NodeType | 'all';

interface TreeViewHeaderProps {
  searchQuery: string;
  onSearchChange: (value: string) => void;
  selectedView: string;
  onViewChange: (value: string) => void;
  showDollars: boolean;
  onShowDollarsChange: (value: boolean) => void;
}

const TreeViewHeader: React.FC<TreeViewHeaderProps> = ({
  searchQuery,
  onSearchChange,
  selectedView,
  onViewChange,
  showDollars,
  onShowDollarsChange,
}) => {
  return (
    <div className="flex items-center gap-2 p-2">
      <TextField
        value={searchQuery}
        onChange={onSearchChange}
        placeholder="Search"
        icon="search"
      />
      <div className="flex items-center gap-2">
        <span className="text-sm text-moon-500">Time</span>
        <Switch.Root
          size="small"
          checked={showDollars}
          onCheckedChange={onShowDollarsChange}
        >
          <Switch.Thumb size="small" checked={showDollars} />
        </Switch.Root>
        <span className="text-sm text-moon-500">Cost</span>
      </div>
    </div>
  );
};

export const FilterableTreeView: React.FC<TraceViewProps> = props => {
  const [searchQuery, setSearchQuery] = useState('');

  const [showDollars, setShowDollars] = useState(false);

  const [filteredCallIds, deemphasizeCallIds] = useMemo(() => {
    const filtered = Object.entries(props.traceTreeFlat)
      .filter(([_, node]) => {
        return searchQuery === '' || 
          getCallDisplayName(node.call).toLowerCase().includes(searchQuery.toLowerCase());
        
      })
      .map(([id]) => id);
    
      // Recursively include all ancestors of the filtered calls

      const foundCallIds = new Set<string>(filtered);
      const itemsToProcess = [...filtered];
      const filteredCallIdsSet = new Set(filtered);
      while (itemsToProcess.length > 0) {
        const id = itemsToProcess.shift();
        if (id) {
          const node = props.traceTreeFlat[id];
          if (node.parentId) {
            filteredCallIdsSet.add(node.parentId);
            itemsToProcess.push(node.parentId);
          }
        }
      }

    const deemphasizeCallIds = Array.from(filteredCallIdsSet.difference(foundCallIds));
    return [Array.from(filteredCallIdsSet), deemphasizeCallIds];
  }, [props.traceTreeFlat, searchQuery]);

  return (
    <div className="flex flex-col h-full">
      <TreeViewHeader
        searchQuery={searchQuery}
        onSearchChange={setSearchQuery}
        selectedView="tree"
        onViewChange={() => {}}
        showDollars={showDollars}
        onShowDollarsChange={setShowDollars}
      />
      <div className="flex-1 overflow-hidden">
        <TreeView
          {...props}
          filterCallIds={filteredCallIds}
          deemphasizeCallIds={deemphasizeCallIds}
        />
      </div>
    </div>
  );
};


export const TreeView: React.FC<
  TraceViewProps & {filterCallIds?: string[], deemphasizeCallIds?: string[]}
> = ({traceTreeFlat, selectedCallId, onCallSelect, filterCallIds, deemphasizeCallIds}) => {
  const {containerRef, width} = useContainerWidth();
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
    <div className="h-full overflow-hidden" ref={containerRef}>
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
              deemphasizeCallIds={deemphasizeCallIds}
              containerWidth={width}
            />
          ))}
        </div>
      </div>
    </div>
  );
};
