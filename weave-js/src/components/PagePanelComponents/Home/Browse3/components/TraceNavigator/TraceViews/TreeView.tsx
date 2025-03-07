import {Button} from '@wandb/weave/components/Button';
import {TextField} from '@wandb/weave/components/Form/TextField';
import {Icon, IconName} from '@wandb/weave/components/Icon';
import {
  getTagColorClass,
  IconOnlyPill,
  TagColorName,
} from '@wandb/weave/components/Tag';
import React, {useEffect, useMemo, useRef, useState} from 'react';
import {AutoSizer, List} from 'react-virtualized';

import {
  getCostFromCostData,
  getTokensFromUsage,
  TraceStat,
} from '../../../pages/CallPage/cost';
import {
  CallStatusType,
  STATUS_INFO,
  StatusChip,
} from '../../../pages/common/StatusChip';
import {TraceCallSchema} from '../../../pages/wfReactInterface/traceServerClientTypes';
import {
  parseSpanName,
  traceCallStatusCode,
} from '../../../pages/wfReactInterface/tsDataModelHooks';
import TraceScrubber, {ScrubberOption} from '../TraceScrubber';
import {TraceTreeFlat, TraceViewProps} from './types';
import {formatDuration, getCallDisplayName} from './utils';

interface FlattenedNode {
  id: string;
  call: TraceCallSchema;
  level: number;
  isExpanded: boolean;
  isVisible: boolean;
  childrenIds: string[];
  hasDescendantErrors: boolean;
}

interface TreeNodeProps {
  node: FlattenedNode;
  style: React.CSSProperties;
  focusedCallId?: string;
  setFocusedCallId: (id: string) => void;
  rootCallId?: string;
  setRootCallId: (id: string) => void;
  onToggleExpand: (id: string) => void;
  deemphasizeCallIds?: string[];
}

type NodeType =
  | 'agent'
  | 'tool'
  | 'llm'
  | 'model'
  | 'evaluation'
  | 'scorer'
  | 'none';

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
    case 'scorer':
      return 'checkmark-circle';
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
    case 'scorer':
      return 'magenta';
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
  if (spanName.includes('score')) {
    return 'scorer';
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

const TreeNode: React.FC<TreeNodeProps> = ({
  node,
  style,
  focusedCallId,
  setFocusedCallId,
  setRootCallId,
  onToggleExpand,
  deemphasizeCallIds,
}) => {
  const {id, call, level, isExpanded, childrenIds, hasDescendantErrors} = node;
  const duration = call.ended_at
    ? Date.parse(call.ended_at) - Date.parse(call.started_at)
    : null;

  const spanName = parseSpanName(call.op_name);
  const typeName = spanNameToTypeHeuristic(spanName);
  const {cost, costToolTipContent} = getCostFromCostData(
    call.summary?.weave?.costs
  );
  const {tokens, tokenToolTipContent} = getTokensFromUsage(call.summary?.usage);

  const opTypeColor = opTypeToColor(typeName);
  const chevronIcon: IconName = isExpanded ? 'chevron-down' : 'chevron-next';
  const isDeemphasized = deemphasizeCallIds?.includes(id);
  const hasChildren = childrenIds.length > 0;
  let statusCode: CallStatusType = traceCallStatusCode(call);
  if (hasDescendantErrors && statusCode === 'SUCCESS') {
    statusCode = 'DESCENDANT_ERROR';
  }
  const showTypeIcon = true;
  const showDuration = true;
  const showStatusIcon = true;
  const usageIconsOnly = false;
  const indentMultiplier = 10;

  return (
    <div style={style}>
      <Button
        variant={id === focusedCallId ? 'secondary' : 'ghost'}
        active={id === focusedCallId}
        onClick={() => setFocusedCallId(id)}
        onDoubleClick={() => setRootCallId(id)}
        className="h-[32px] w-full justify-start px-8 text-left text-sm"
        style={{
          opacity: isDeemphasized ? 0.6 : 1,
        }}>
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
          <div className="flex min-w-0 flex-1 items-center">
            <div style={{minWidth: level * indentMultiplier}} />
            {hasChildren ? (
              <Icon
                name={chevronIcon}
                size="small"
                onClick={(e: React.MouseEvent) => {
                  e.stopPropagation();
                  onToggleExpand(id);
                }}
                className="p-0.5 shrink-0 cursor-pointer rounded hover:bg-moon-200"
              />
            ) : (
              <div className="w-4" />
            )}

            <div className="ml-2 truncate font-medium">
              {getCallDisplayName(call)}
            </div>
          </div>

          <div className="ml-8 flex shrink-0 items-center gap-8 text-xs text-moon-400">
            {showDuration && (
              <>
                {usageIconsOnly ? (
                  <>
                    <div className="w-20 text-right">
                      {cost && (
                        <TraceStat
                          label={''}
                          tooltip={
                            <>
                              {cost && costToolTipContent}
                              <br />
                              {tokens && tokenToolTipContent}
                            </>
                          }
                          icon="credit-card-payment"
                          className="text-xs text-moon-400"
                        />
                      )}
                    </div>
                  </>
                ) : (
                  <>
                    {cost && (
                      <div className="w-64 text-right">
                        <TraceStat
                          label={cost}
                          tooltip={costToolTipContent}
                          icon="credit-card-payment"
                          className="text-xs text-moon-400"
                        />
                      </div>
                    )}
                    {tokens && (
                      <div className="w-64 text-right">
                        <TraceStat
                          icon="database-artifacts"
                          label={tokens.toString()}
                          tooltip={tokenToolTipContent}
                          className="text-xs text-moon-400"
                        />
                      </div>
                    )}
                  </>
                )}
                <div className="w-32 text-right">
                  {duration !== null ? formatDuration(duration) : ''}
                </div>
              </>
            )}

            {showStatusIcon ? (
              <StatusChip value={statusCode} iconOnly />
            ) : (
              <div
                className={`h-8 w-8 rounded-full ${getTagColorClass(
                  STATUS_INFO[statusCode].color
                )}`}
              />
            )}
          </div>
        </div>
      </Button>
    </div>
  );
};

interface TreeViewHeaderProps {
  searchQuery: string;
  onSearchChange: (value: string) => void;
}

const TreeViewHeader: React.FC<TreeViewHeaderProps> = ({
  searchQuery,
  onSearchChange,
}) => {
  return (
    <div className="flex items-center px-8 py-4 text-sm">
      <TextField
        value={searchQuery}
        onChange={onSearchChange}
        placeholder="Filter by op name"
        icon="filter-alt"
        extraActions={
          searchQuery !== '' && (
            <div className="mr-6 cursor-pointer rounded-sm p-1 hover:bg-moon-200">
              <Icon
                name="close"
                size="small"
                onClick={() => onSearchChange('')}
              />
            </div>
          )
        }
      />
    </div>
  );
};

export const FilterableTreeView: React.FC<TraceViewProps> = props => {
  const [searchQuery, setSearchQuery] = useState('');

  const [matchedCallIds, filteredCallIds, deemphasizeCallIds] = useMemo(() => {
    const filtered = Object.entries(props.traceTreeFlat)
      .filter(([_, node]) => {
        return (
          searchQuery === '' ||
          getCallDisplayName(node.call)
            .toLowerCase()
            .includes(searchQuery.toLowerCase())
        );
      })
      .map(([id]) => id);

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

    return [
      filtered,
      Array.from(filteredCallIdsSet),
      Array.from(
        new Set([...filteredCallIdsSet].filter(x => !foundCallIds.has(x)))
      ),
    ];
  }, [props.traceTreeFlat, searchQuery]);

  const scrubbers: ScrubberOption[] = useMemo(() => {
    if (searchQuery === '') {
      return ['timeline', 'peer', 'sibling', 'stack'];
    }
    return ['timeline'];
  }, [searchQuery]);

  // Derived data
  const traceTreeFlat = useMemo(() => {
    if (searchQuery === '') {
      return props.traceTreeFlat;
    }
    const matched = new Set<string>(matchedCallIds);
    return Object.fromEntries(
      Object.entries(props.traceTreeFlat).filter(([_, node]) => {
        return matched.has(node.id);
      })
    );
  }, [matchedCallIds, props.traceTreeFlat, searchQuery]);

  return (
    <div className="flex h-full flex-col">
      <TreeViewHeader
        searchQuery={searchQuery}
        onSearchChange={setSearchQuery}
      />
      <div className="flex-1 overflow-hidden">
        <TreeView
          {...props}
          filterCallIds={filteredCallIds}
          deemphasizeCallIds={deemphasizeCallIds}
        />
      </div>
      <TraceScrubber
        {...props}
        allowedScrubbers={scrubbers}
        traceTreeFlat={traceTreeFlat}
      />
    </div>
  );
};

export const TreeView: React.FC<
  TraceViewProps & {
    filterCallIds?: string[];
    deemphasizeCallIds?: string[];
  }
> = ({
  traceTreeFlat,
  focusedCallId,
  setFocusedCallId,
  filterCallIds,
  deemphasizeCallIds,
  setRootCallId,
}) => {
  // Initialize expandedNodes with all node IDs
  const [expandedNodes, setExpandedNodes] = useState<Set<string>>(
    () => new Set(Object.keys(traceTreeFlat))
  );

  const filterSet = useMemo(
    () => (filterCallIds ? new Set(filterCallIds) : undefined),
    [filterCallIds]
  );

  const listRef = useRef<List>(null);

  const rootNodes = useMemo(() => {
    if (!filterCallIds || filterCallIds.length === 0) {
      return Object.values(traceTreeFlat).filter(
        node => !node.parentId || !traceTreeFlat[node.parentId]
      );
    }

    const filterIdSet = new Set(filterCallIds);
    return Object.values(traceTreeFlat).filter(node => {
      if (!filterIdSet.has(node.id)) {
        return false;
      }
      return (
        !node.parentId ||
        !traceTreeFlat[node.parentId] ||
        !filterIdSet.has(node.parentId)
      );
    });
  }, [traceTreeFlat, filterCallIds]);

  const flattenedNodes = useMemo(() => {
    const result: FlattenedNode[] = [];
    const processNode = (node: TraceTreeFlat[string], level: number) => {
      const isExpanded = expandedNodes.has(node.id);
      const filteredChildren = node.childrenIds.filter(childId => {
        return !filterSet || filterSet.has(childId);
      });
      result.push({
        id: node.id,
        call: node.call,
        level,
        isExpanded,
        isVisible: true,
        childrenIds: filteredChildren,
        hasDescendantErrors: node.descendantHasErrors,
      });

      if (isExpanded) {
        filteredChildren.forEach((childId: string) => {
          const child = traceTreeFlat[childId];
          if (child && (!filterSet || filterSet.has(childId))) {
            processNode(child, level + 1);
          }
        });
      }
    };

    rootNodes.forEach(node => processNode(node, 0));
    return result;
  }, [rootNodes, traceTreeFlat, expandedNodes, filterSet]);

  const handleToggleExpand = (id: string) => {
    const newExpandedNodes = new Set(expandedNodes);
    if (newExpandedNodes.has(id)) {
      newExpandedNodes.delete(id);
    } else {
      newExpandedNodes.add(id);
    }
    setExpandedNodes(newExpandedNodes);
  };

  const rowRenderer = ({index, style}: any) => {
    const node = flattenedNodes[index];
    return (
      <TreeNode
        key={node.id}
        node={node}
        style={style}
        focusedCallId={focusedCallId}
        setFocusedCallId={setFocusedCallId}
        setRootCallId={setRootCallId}
        onToggleExpand={handleToggleExpand}
        deemphasizeCallIds={deemphasizeCallIds}
      />
    );
  };

  // Scroll when selectedCallId changes
  useEffect(() => {
    const scrollToSelectedRow = () => {
      if (!focusedCallId || !listRef.current) {
        return;
      }

      const selectedIndex = flattenedNodes.findIndex(
        (node: FlattenedNode) => node.id === focusedCallId
      );
      if (selectedIndex === -1) {
        return;
      }

      listRef.current.scrollToRow(selectedIndex);
    };

    const timer = setTimeout(scrollToSelectedRow, 0);
    return () => clearTimeout(timer);
  }, [focusedCallId, flattenedNodes]);

  return (
    <div className="h-full overflow-hidden">
      <AutoSizer>
        {({width, height}) => (
          <List
            ref={listRef}
            width={width}
            height={height}
            rowCount={flattenedNodes.length}
            rowHeight={32}
            rowRenderer={rowRenderer}
            overscanRowCount={10}
            scrollToAlignment="auto"
          />
        )}
      </AutoSizer>
    </div>
  );
};
