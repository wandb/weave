import {MOON_900, TEAL_300} from '@wandb/weave/common/css/color.styles';
import {Button} from '@wandb/weave/components/Button';
import {TextField} from '@wandb/weave/components/Form/TextField';
import {Icon, IconName} from '@wandb/weave/components/Icon';
import {Tooltip} from '@wandb/weave/components/Tooltip';
import classNames from 'classnames';
import React, {useEffect, useMemo, useRef, useState} from 'react';
import {AutoSizer, List} from 'react-virtualized';

import {
  getCostFromCostData,
  getTokensFromUsage,
  TraceStat,
} from '../../../pages/CallPage/cost';
import {CallStatusType, StatusChip} from '../../../pages/common/StatusChip';
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
  searchQuery?: string;
}

const TreeNode: React.FC<TreeNodeProps> = ({
  node,
  style,
  focusedCallId,
  setFocusedCallId,
  setRootCallId,
  onToggleExpand,
  deemphasizeCallIds,
  searchQuery,
}) => {
  const {id, call, level, isExpanded, childrenIds, hasDescendantErrors} = node;
  const duration = call.ended_at
    ? Date.parse(call.ended_at) - Date.parse(call.started_at)
    : null;

  const {costNum, costToolTipContent} = getCostFromCostData(
    call.summary?.weave?.costs
  );
  const {tokens, tokenToolTipContent} = getTokensFromUsage(call.summary?.usage);

  const displayName = getCallDisplayName(call);
  const renderHighlightedText = () => {
    if (!searchQuery) {
      return displayName;
    }
    const searchLower = searchQuery.toLowerCase();
    const textLower = displayName.toLowerCase();

    // Note: could highlight multiple matches for better UX
    const index = textLower.indexOf(searchLower);

    if (index === -1) {
      return displayName;
    }

    return (
      <>
        {displayName.slice(0, index)}
        <span
          className={classNames(
            'font-semibold',
            'text-teal-600',
            'dark:text-teal-500'
          )}>
          {displayName.slice(index, index + searchQuery.length)}
        </span>
        {displayName.slice(index + searchQuery.length)}
      </>
    );
  };

  const chevronIcon: IconName = isExpanded ? 'chevron-down' : 'chevron-next';
  const isDeemphasized = deemphasizeCallIds?.includes(id);
  const hasChildren = childrenIds.length > 0;
  let statusCode: CallStatusType = traceCallStatusCode(call);
  if (hasDescendantErrors && statusCode === 'SUCCESS') {
    statusCode = 'DESCENDANT_ERROR';
  }
  const indentMultiplier = 14;

  return (
    <div style={style}>
      <Button
        variant="ghost"
        style={{
          opacity: isDeemphasized ? 0.7 : 1,
          backgroundColor: id === focusedCallId ? `${TEAL_300}52` : undefined,
          color: id === focusedCallId ? MOON_900 : undefined,
        }}
        onClick={() => setFocusedCallId(id)}
        onDoubleClick={() => setRootCallId(id)}
        className="h-[38px] w-full justify-start rounded-none px-8 text-left text-sm hover:bg-moon-150">
        <div className="relative flex w-full items-center justify-between gap-8">
          <div className="flex min-w-0 flex-1 items-center">
            <div
              style={{marginLeft: level * indentMultiplier}}
              className={`h-[38px]`}
            />
            {/* Render vertical lines for each level of hierarchy */}
            {Array.from({length: level}).map((_, idx) => (
              <div
                key={`line-${idx}`}
                style={{left: idx * indentMultiplier, marginLeft: 8}}
                className="absolute top-0 h-full w-px border-l border-moon-300"
              />
            ))}
            {hasChildren && (
              <Icon
                name={chevronIcon}
                size="small"
                onClick={(e: React.MouseEvent) => {
                  e.stopPropagation();
                  onToggleExpand(id);
                }}
                className="p-0.5 shrink-0 cursor-pointer rounded hover:bg-moon-300"
              />
            )}
            <div className="truncate pl-4 font-medium">
              <Tooltip
                trigger={
                  <div className="truncate">{renderHighlightedText()}</div>
                }
                content={<span>{displayName}</span>}
              />
            </div>
          </div>

          <div className="ml-8 flex shrink-0 items-center gap-4 text-xs text-moon-400">
            <div className="flex items-center gap-2 text-right">
              {costNum !== undefined && (
                <TraceStat
                  label={costNum !== 0 && costNum < 0.01 ? '<$0.01' : `$${costNum.toFixed(2)}`}
                  tooltip={
                    <div className="text-white-800">
                      {costToolTipContent}
                      {tokens && (
                        <>
                          <br />
                          <span style={{fontWeight: 600}}>
                            Estimated tokens
                          </span>
                        </>
                      )}
                      {tokens && tokenToolTipContent}
                    </div>
                  }
                  className="text-xs text-moon-400"
                />
              )}
              {duration !== null && (
                <span className="text-moon-400 min-w-[34px]">{formatDuration(duration)}</span>
              )}
            </div>
            <StatusChip value={statusCode} iconOnly />
          </div>
        </div>
      </Button>
    </div>
  );
};

interface TreeViewHeaderProps {
  searchQuery: string;
  onSearchChange: (value: string) => void;
  strictSearch: boolean;
  onToggleStrictSearch: () => void;
}

const TreeViewHeader: React.FC<TreeViewHeaderProps> = ({
  searchQuery,
  onSearchChange,
  strictSearch,
  onToggleStrictSearch,
}) => {
  return (
    <div className="flex items-center p-8 text-sm">
      <TextField
        value={searchQuery}
        onChange={onSearchChange}
        placeholder="Filter by op name..."
        icon="filter-alt"
        extraActions={
          searchQuery !== '' && (
            <>
              <Button
                variant="ghost"
                size="small"
                onClick={onToggleStrictSearch}
                tooltip={
                  strictSearch
                    ? '(Strict) Only show matching nodes'
                    : '(Loose) Show children of matching nodes'
                }
                className={strictSearch ? 'mr-2' : 'mr-2 text-moon-500'}
                active={strictSearch}>
                Strict
              </Button>
              <Button
                variant="ghost"
                size="small"
                icon="close"
                onClick={() => onSearchChange('')}
                className="mr-6"
              />
            </>
          )
        }
      />
    </div>
  );
};

export const FilterableTreeView: React.FC<TraceViewProps> = props => {
  const [searchQuery, setSearchQuery] = useState('');
  const [strictSearch, setStrictSearch] = useState(false);

  const [matchedCallIds, filteredCallIds, deemphasizeCallIds] = useMemo(() => {
    // First find direct matches
    const directMatches = Object.entries(props.traceTreeFlat)
      .filter(([_, node]) => {
        return (
          searchQuery === '' ||
          getCallDisplayName(node.call)
            .toLowerCase()
            .includes(searchQuery.toLowerCase())
        );
      })
      .map(([id]) => id);

    const foundCallIds = new Set<string>(directMatches);
    const filteredCallIdsSet = new Set(directMatches);

    // Process queue for both upward (parents) and downward (children)
    const itemsToProcess = [...directMatches];

    while (itemsToProcess.length > 0) {
      const id = itemsToProcess.shift();
      if (id) {
        const node = props.traceTreeFlat[id];

        // Add parents
        if (node.parentId) {
          filteredCallIdsSet.add(node.parentId);
          if (!foundCallIds.has(node.parentId)) {
            itemsToProcess.push(node.parentId);
          }
        }

        // Only add children of direct matches if not in strict search mode
        // Don't add children of parent nodes that were added just to show the path
        if (foundCallIds.has(id) && !strictSearch) {
          // Add all children recursively
          const addChildren = (nodeId: string) => {
            const currentNode = props.traceTreeFlat[nodeId];
            if (currentNode && currentNode.childrenIds) {
              for (const childId of currentNode.childrenIds) {
                if (!filteredCallIdsSet.has(childId)) {
                  filteredCallIdsSet.add(childId);
                  addChildren(childId);
                }
              }
            }
          };

          addChildren(id);
        }
      }
    }

    return [
      directMatches,
      Array.from(filteredCallIdsSet),
      Array.from(
        new Set([...filteredCallIdsSet].filter(x => !foundCallIds.has(x)))
      ),
    ];
  }, [props.traceTreeFlat, searchQuery, strictSearch]);

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
    <div className="flex h-full flex-col overflow-hidden">
      <TreeViewHeader
        searchQuery={searchQuery}
        onSearchChange={setSearchQuery}
        strictSearch={strictSearch}
        onToggleStrictSearch={() => setStrictSearch(!strictSearch)}
      />
      <div className="flex-1 overflow-hidden">
        <TreeView
          {...props}
          filterCallIds={filteredCallIds}
          deemphasizeCallIds={deemphasizeCallIds}
          searchQuery={searchQuery}
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
    searchQuery?: string;
  }
> = ({
  traceTreeFlat,
  focusedCallId,
  setFocusedCallId,
  filterCallIds,
  deemphasizeCallIds,
  setRootCallId,
  searchQuery,
}) => {
  // Initialize expandedNodes with all node IDs
  const [collapsedNodes, setCollapsedNodes] = useState<Set<string>>(
    () => new Set([])
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
      const isExpanded = !collapsedNodes.has(node.id);
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
  }, [rootNodes, traceTreeFlat, collapsedNodes, filterSet]);

  const handleToggleExpand = (id: string) => {
    const newExpandedNodes = new Set(collapsedNodes);
    if (newExpandedNodes.has(id)) {
      newExpandedNodes.delete(id);
    } else {
      newExpandedNodes.add(id);
    }
    setCollapsedNodes(newExpandedNodes);
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
        searchQuery={searchQuery}
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
            rowHeight={38}
            rowRenderer={rowRenderer}
            overscanRowCount={10}
            scrollToAlignment="auto"
          />
        )}
      </AutoSizer>
    </div>
  );
};
